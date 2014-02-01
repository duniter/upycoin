#!/usr/bin/env python3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
# Caner Candan <caner@candan.fr>, http://caner.candan.fr
#

from pprint import pprint
import\
    ucoin, json, logging, argparse, sys,\
    gnupg, hashlib, re, datetime as dt,\
    webbrowser, math
from collections import OrderedDict
from flask import\
    Flask, request, render_template,\
    jsonify, redirect, abort, url_for,\
    flash, Blueprint
from flask.views import MethodView
from io import StringIO
from werkzeug.contrib.cache import SimpleCache

logger = logging.getLogger("wallets")

bp = Blueprint('wallets', __name__, static_folder='static', template_folder='templates')
cache = SimpleCache()

def compute_dividend_remainders(pgp_fingerprint):
    remainders = {}
    for am in ucoin.hdc.amendments.List().get():
        if not am['dividend']: continue
        if not am['dividend']: continue
        dividend_sum = 0
        for x in ucoin.hdc.transactions.sender.issuance.Dividend(pgp_fingerprint, am['number']).get():
            __sum = 0
            for coin in x['value']['transaction']['coins']:
                base, power = coin['id'].split('-')[2:4]
                __sum += int(base) * 10**int(power)
            dividend_sum += __sum

        if am['dividend'] > dividend_sum:
            remainders[int(am['number'])] = am['dividend'] - dividend_sum
    return remainders

@bp.app_template_filter('split')
def split_filter(s, sep=' '):
    return s.split(sep)

@bp.app_template_filter('compute_coin')
def compute_coin_filter(coin):
    fpr, number, base, power, origin, origin_number = coin.split('-')
    return int(base)*10**int(power)

@bp.app_template_filter('timestamp2date')
def timestamp2date_filter(timestamp, format='%d-%m-%Y %H:%M:%S'):
    return dt.datetime.fromtimestamp(timestamp).strftime(format)

@bp.route('/')
def home():
    return render_template('wallets/index.html', settings=ucoin.settings)

@bp.route('/new')
def new():
    return render_template('wallets/new.html', settings=ucoin.settings)

@bp.route('/new/create')
def new_create():
    __input = 'Key-Type: %(type)s\nName-Email: %(email)s\nName-Real: %(realm)s\nKey-Length: %(length)s\n%%commit\n' % request.args
    newkey = ucoin.settings['gpg'].gen_key(__input)
    return jsonify(result="Your new key (%s) has been successfully created." % newkey.fingerprint)

def get_transactions(pgp_fingerprint, fct, key_prefix, begin=None, end=None):
    k = '%s_transactions_%s' % (key_prefix, pgp_fingerprint)
    v = cache.get(k)
    if v is None:
        v = list(fct(pgp_fingerprint, begin=begin, end=end).get())
        v.sort(key=lambda x: x['value']['transaction']['sigDate'], reverse=True)
        cache.set(k, v, timeout=5*60)
    return v

from math import ceil

class Pagination(object):

    def __init__(self, page, per_page, total_count):
        self.page = page
        self.per_page = per_page
        self.total_count = total_count

    @property
    def pages(self):
        return int(ceil(self.total_count / float(self.per_page)))

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    def iter_pages(self, left_edge=2, left_current=2,
                   right_current=5, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and \
                num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num

PER_PAGE = 10

@bp.app_template_global('url_for_other_page')
def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)

@bp.route('/<pgp_fingerprint>/history')
@bp.route('/<pgp_fingerprint>/history/<type>')
@bp.route('/<pgp_fingerprint>/history/page/<int:page>')
@bp.route('/<pgp_fingerprint>/history/<type>/page/<int:page>')
def history(pgp_fingerprint, type='all', page=1):
    recipient = get_transactions(pgp_fingerprint, ucoin.hdc.transactions.Recipient, 'recipient')
    sender = get_transactions(pgp_fingerprint, ucoin.hdc.transactions.Sender, 'sender')
    count = max(len(recipient), len(sender))

    begin = (page-1)*PER_PAGE
    end = begin+(PER_PAGE-1)

    pagination = Pagination(page, PER_PAGE, count)

    return render_template('wallets/history.html',
                           settings=ucoin.settings,
                           key=ucoin.settings['secret_keys'].get(pgp_fingerprint),
                           recipient=recipient[begin:end],
                           sender=sender[begin:end],
                           pagination=pagination,
                           type=type, page=page,
                           clist=ucoin.wrappers.CoinsList(pgp_fingerprint)())

@bp.route('/<pgp_fingerprint>/history/refresh')
@bp.route('/<pgp_fingerprint>/history/refresh/<type>')
@bp.route('/<pgp_fingerprint>/history/refresh/page/<int:page>')
@bp.route('/<pgp_fingerprint>/history/refresh/<type>/page/<int:page>')
def history_refresh(pgp_fingerprint, type='all', page=1):
    k = 'sender_transactions_%s' % pgp_fingerprint; cache.set(k, None)
    k = 'recipient_transactions_%s' % pgp_fingerprint; cache.set(k, None)
    flash(u'History refreshed', 'info')
    return redirect(url_for('.history', pgp_fingerprint=pgp_fingerprint, type=type, page=page))

@bp.route('/<pgp_fingerprint>/transfer', methods=['GET', 'POST'])
def transfer(pgp_fingerprint):
    balance, __clist = ucoin.wrappers.CoinsList(pgp_fingerprint)()

    if request.method == 'GET':
        return render_template('wallets/transfer.html',
                               settings=ucoin.settings,
                               key=ucoin.settings['secret_keys'].get(pgp_fingerprint),
                               clist=(balance,__clist))

    amounts = [x['amount'] for x in __clist]
    amounts.sort()
    amounts.reverse()

    recipient = request.form.get('recipient')
    amount = request.form.get('amount', type=int)
    message = request.form.get('message', '')

    if not recipient or not amount:
        flash('recipient or amount field is missing.', 'error')
        return redirect(url_for('.transfer', pgp_fingerprint=pgp_fingerprint))

    if amount > balance:
        flash('amount is higher than available balance (%d > %d).' % (amount, balance), 'error')
        return redirect(url_for('.transfer', pgp_fingerprint=pgp_fingerprint))

    coins = []
    total = 0
    for coin in amounts:
        if total >= amount: break
        if total+coin <= amount:
            coins.append(coin)
            total += coin

    if sum(coins) != amount:
        flash('this amount cannot be reached with existing coins in your wallet.', 'error')
        return redirect(url_for('.transfer', pgp_fingerprint=pgp_fingerprint))

    coins = ucoin.wrappers.CoinsGet(pgp_fingerprint, coins)()

    transfer = ucoin.wrappers.Transfer(pgp_fingerprint, recipient, coins, message)

    if not transfer():
        flash(u'Transfer error', 'error')
    else:
        flash(u'Transfer succed', 'success')

    return redirect(url_for('.transfer', pgp_fingerprint=pgp_fingerprint))

@bp.route('/public_keys')
def public_keys():
    keys = ucoin.settings['public_keys']
    for k,v in keys.items():
        v['value'] = v['fingerprint']
        v['tokens'] = v['uids']
        v['name'] = v['uids'][0]
    return json.dumps(list(keys.values()))

@bp.route('/contacts')
def contacts():
    return render_template('wallets/contacts.html',
                           settings=ucoin.settings)

@bp.route('/<pgp_fingerprint>/issuance', methods=['GET', 'POST'])
def issuance(pgp_fingerprint):
    k = 'remainders_%s' % pgp_fingerprint
    remainders = cache.get(k)
    if remainders is None:
        remainders = compute_dividend_remainders(pgp_fingerprint)
        cache.set(k, remainders, timeout=5*60)

    if not remainders:
        return render_template('wallets/no_issuance.html',
                               settings=ucoin.settings,
                               key=ucoin.settings['secret_keys'].get(pgp_fingerprint))

    remainder = sum(remainders.values())
    max_remainder = max(remainders.values()) if remainders.values() else 0

    def count_coins(coin):
        count = 0
        for r in remainders.values():
            if r >= coin: count += int(r/coin)
        return count

    coins = []
    for power in range(10):
        for base in [1,2,5]:
            coin = base*(10**power)
            if coin > max_remainder: break
            coins.append((coin,count_coins(coin)))

    if request.method == 'GET':
        return render_template('wallets/issuance.html',
                               settings=ucoin.settings,
                               key=ucoin.settings['secret_keys'].get(pgp_fingerprint),
                               remainders=remainders, remainder=remainder,
                               max_remainder=max_remainder, coins=coins)

    quantities = []
    for coin, count in reversed(coins):
        qte = request.form.get('coin_%d' % coin, type=int)
        if qte: quantities.append((coin, qte))

    issuances = {}

    for am in remainders:
        issuances[am] = issuance = []

        for i in range(len(quantities)):
            coin, qte = quantities[i]
            if not qte: continue

            if coin <= remainders[am]:
                new_qte = int(remainders[am]/coin)
                if new_qte > qte: new_qte = qte
                remainders[am] -= coin*new_qte
                quantities[i] = (coin,qte-new_qte)

                for i in range(new_qte):
                    power = int(math.log10(coin))
                    issuance.append('%d,%d' % (coin/10**power, power))

    for am, coins in issuances.items():
        issue = ucoin.wrappers.Issue(pgp_fingerprint, am, coins)
        if not issue():
            flash(u'Issuance error', 'error')
            break

    flash('The issuance was completed.', 'success')
    cache.set(k, None)

    return redirect(url_for('.issuance', pgp_fingerprint=pgp_fingerprint))
