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
    flash
from flask.views import MethodView
from io import StringIO
from werkzeug.contrib.cache import SimpleCache

logger = logging.getLogger("wallets")

def get_sender_transactions(pgp_fingerprint, cache=None):
    k = 'sender_transactions_%s' % pgp_fingerprint
    rv = cache.get(k)
    if rv is None:
        rv = list(ucoin.hdc.transactions.Sender(pgp_fingerprint).get())
        __dict = {}
        for item in rv: __dict[item['value']['transaction']['number']] = item['value']['transaction']
        rv = __dict
        cache.set(k, rv, timeout=5*60)
    return rv

def get_recipient_transactions(pgp_fingerprint, cache=None):
    k = 'recipient_transactions_%s' % pgp_fingerprint
    rv = cache.get(k)
    if rv is None:
        rv = list(ucoin.hdc.transactions.Recipient(pgp_fingerprint).get())
        __dict = {}
        for item in rv: __dict[item['value']['transaction']['number']] = item['value']['transaction']
        rv = __dict
        cache.set(k, rv, timeout=5*60)
    return rv

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

def register(app, cache=None):
    @app.template_filter('split')
    def split_filter(s, sep=' '):
        return s.split(sep)

    @app.template_filter('compute_coin')
    def compute_coin_filter(coin):
        fpr, number, base, power, origin, origin_number = coin.split('-')
        return int(base)*10**int(power)

    @app.route('/')
    @app.route('/wallets')
    def wallets():
        return render_template('wallets/index.html', settings=ucoin.settings)

    @app.route('/wallets/new')
    def new_wallet():
        return render_template('wallets/new.html', settings=ucoin.settings)

    @app.route('/wallets/new/create')
    def new_wallet_create():
        __input = 'Key-Type: %(type)s\nName-Email: %(email)s\nName-Real: %(realm)s\nKey-Length: %(length)s\n%%commit\n' % request.args
        newkey = ucoin.settings['gpg'].gen_key(__input)
        return jsonify(result="Your new key (%s) has been successfully created." % newkey.fingerprint)

    @app.route('/wallets/<pgp_fingerprint>/history')
    @app.route('/wallets/<pgp_fingerprint>/history/<type>')
    def wallet_history(pgp_fingerprint, type='all'):
        sender = get_sender_transactions(pgp_fingerprint, cache)
        recipient = get_recipient_transactions(pgp_fingerprint, cache)

        return render_template('wallets/history.html',
                               settings=ucoin.settings,
                               key=ucoin.settings['secret_keys'].get(pgp_fingerprint),
                               sender=sender,
                               recipient=recipient,
                               type=type,
                               clist=ucoin.wrappers.CoinsList(pgp_fingerprint)())

    @app.route('/wallets/<pgp_fingerprint>/history/refresh')
    @app.route('/wallets/<pgp_fingerprint>/history/refresh/<type>')
    def wallet_history_refresh(pgp_fingerprint, type='all'):
        k = 'sender_transactions_%s' % pgp_fingerprint; cache.set(k, None)
        k = 'recipient_transactions_%s' % pgp_fingerprint; cache.set(k, None)
        flash(u'History refreshed', 'info')
        return redirect(url_for('wallet_history', pgp_fingerprint=pgp_fingerprint, type=type))

    @app.route('/wallets/<pgp_fingerprint>/transfer', methods=['GET', 'POST'])
    def wallet_transfer(pgp_fingerprint):
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
            return redirect(url_for('wallet_transfer', pgp_fingerprint=pgp_fingerprint))

        if amount > balance:
            flash('amount is higher than available balance (%d > %d).' % (amount, balance), 'error')
            return redirect(url_for('wallet_transfer', pgp_fingerprint=pgp_fingerprint))

        coins = []
        total = 0
        for coin in amounts:
            if total >= amount: break
            if total+coin <= amount:
                coins.append(coin)
                total += coin

        if sum(coins) != amount:
            flash('this amount cannot be reached with existing coins in your wallet.', 'error')
            return redirect(url_for('wallet_transfer', pgp_fingerprint=pgp_fingerprint))

        coins = ucoin.wrappers.CoinsGet(pgp_fingerprint, coins)()

        transfer = ucoin.wrappers.Transfer(pgp_fingerprint, recipient, coins, message)

        if not transfer():
            flash(u'Transfer error', 'error')
        else:
            flash(u'Transfer succed', 'success')

        return redirect(url_for('wallet_transfer', pgp_fingerprint=pgp_fingerprint))

    @app.route('/wallets/public_keys')
    def wallet_public_keys():
        keys = ucoin.settings['public_keys']
        for k,v in keys.items():
            v['value'] = v['fingerprint']
            v['tokens'] = v['uids']
            v['name'] = v['uids'][0]
        return json.dumps(list(keys.values()))

    @app.route('/wallets/contacts')
    def wallet_contacts():
        return render_template('wallets/contacts.html',
                               settings=ucoin.settings)

    @app.route('/wallets/<pgp_fingerprint>/issuance', methods=['GET', 'POST'])
    def wallet_issuance(pgp_fingerprint):
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

        return redirect(url_for('wallet_issuance', pgp_fingerprint=pgp_fingerprint))
