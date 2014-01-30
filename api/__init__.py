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
from io import StringIO
from werkzeug.contrib.cache import SimpleCache

logger = logging.getLogger("api")

def format_amendment(am):
    res = """\
Version\t\t\t%(version)s
Currency\t\t%(currency)s
Number\t\t\t%(number)s
GeneratedOn\t\t%(generated)s
UniversalDividend\t%(dividend)s
NextRequiredVotes\t%(nextVotes)s
PreviousHash\t\t%(previousHash)s
MembersRoot\t\t%(membersRoot)s
MembersCount\t\t%(membersCount)s
""" % am

    if am['membersChanges']:
        res += 'MembersChanges\n'
        for x in am['membersChanges']: res += '%s\n' % x

    res += """\
VotersRoot\t\t%(votersRoot)s
VotersCount\t\t%(votersCount)s
""" % am

    if am['votersChanges']:
        res += 'VotersChanges\n'
        for x in am['votersChanges']: res += '%s\n' % x

    return res

def render_prettyprint(template_name, result):
    s = StringIO()
    pprint(result, s)
    s = s.getvalue().replace('\\r', '').replace('\\n', '\n')
    return render_template(template_name, result=s, style='prettyprint')

def register(app, cache=None):
    @app.route('/api')
    def api():
        return render_template('api/index.html')

    @app.route('/api/pks/add', methods=['GET', 'POST'])
    def pks_add():
        if request.method == 'GET':
            return render_template('api/result.html', result='POST Method has to be used')

        keytext = request.form.get('keytext')
        keysign = request.form.get('keysign')

        return render_template('api/result.html', result=ucoin.pks.Add().post(keytext=keytext, keysign=keysign))

    @app.route('/api/pks/lookup')
    def pks_lookup():
        search = request.args.get('search', '')
        op = request.args.get('op', 'get')

        return render_template('api/result.html', result=ucoin.pks.Lookup().get(search=search, op=op))

    @app.route('/api/pks/all')
    def pks_all():
        return render_prettyprint('api/result.html', list(ucoin.pks.All().get()))

    @app.route('/api/ucg/pubkey')
    def ucg_pubkey():
        return render_template('api/result.html', result=ucoin.ucg.Pubkey().get(), style='text')

    @app.route('/api/ucg/peering')
    def ucg_peering():
        return render_prettyprint('api/result.html', ucoin.ucg.Peering().get())

    @app.route('/api/ucg/peering/keys')
    def ucg_peering_keys():
        return render_prettyprint('api/result.html', list(ucoin.ucg.peering.Keys().get()))

    @app.route('/api/ucg/peering/peer')
    def ucg_peering_peer():
        return render_prettyprint('api/result.html', ucoin.ucg.peering.Peer().get())

    @app.route('/api/ucg/peering/peers', methods=['GET', 'POST'])
    def ucg_peering_peers():
        if request.method == 'GET':
            return render_prettyprint('api/result.html', list(ucoin.ucg.peering.Peers().get()))

        entry = request.form.get('entry')
        signature = request.form.get('signature')

        return render_prettyprint('api/result.html', ucoin.ucg.peering.Peers().post(entry=entry, signature=signature))

    @app.route('/api/ucg/peering/peers/upstream')
    def ucg_peering_peers_upstream():
        return render_prettyprint('api/result.html', ucoin.ucg.peering.peers.UpStream().get())

    @app.route('/api/ucg/peering/peers/upstream/<pgp_fingerprint>')
    def ucg_peering_peers_upstream_pgp(pgp_fingerprint):
        return render_prettyprint('api/result.html', ucoin.ucg.peering.peers.UpStream(pgp_fingerprint).get())

    @app.route('/api/ucg/peering/peers/downstream')
    def ucg_peering_peers_downstream():
        return render_prettyprint('api/result.html', ucoin.ucg.peering.peers.DownStream().get())

    @app.route('/api/ucg/peering/peers/downstream/<pgp_fingerprint>')
    def ucg_peering_peers_downstream_pgp(pgp_fingerprint):
        return render_prettyprint('api/result.html', ucoin.ucg.peering.peers.DownStream(pgp_fingerprint).get())

    @app.route('/api/ucg/peering/forward', methods=['GET', 'POST'])
    def ucg_peering_forward():
        if request.method == 'GET':
            return render_template('api/result.html', result='POST Method has to be used')

        forward = request.form.get('forward')
        signature = request.form.get('signature')

        return render_prettyprint('api/result.html', ucoin.ucg.peering.Forward().post(forward=forward, signature=signature))

    @app.route('/api/ucg/peering/status', methods=['GET', 'POST'])
    def ucg_peering_status():
        if request.method == 'GET':
            return render_template('api/result.html', result='POST Method has to be used')

        status = request.form.get('status')
        signature = request.form.get('signature')

        return render_prettyprint('api/result.html', ucoin.ucg.peering.Status().post(status=status, signature=signature))

    @app.route('/api/ucg/tht', methods=['GET', 'POST',])
    def ucg_tht():
        if request.method == 'GET':
            return render_prettyprint('api/result.html', list(ucoin.ucg.THT().get()))

        entry = request.form.get('entry')
        signature = request.form.get('signature')

        return render_prettyprint('api/result.html', ucoin.ucg.THT().post(entry=entry, signature=signature))

    @app.route('/api/ucg/tht/<pgp_fingerprint>')
    def ucg_tht_pgp(pgp_fingerprint):
        return render_prettyprint('api/result.html', ucoin.ucg.THT(pgp_fingerprint).get())

    @app.route('/api/hdc/amendments/current')
    def hdc_amendments_current():
        return render_prettyprint('api/result.html', ucoin.hdc.amendments.Current().get())

    @app.route('/api/hdc/amendments/current/votes')
    def hdc_amendments_current_votes():
        return render_prettyprint('api/result.html', list(ucoin.hdc.amendments.CurrentVotes().get()))

    @app.route('/api/hdc/amendments/promoted')
    def hdc_amendments_promoted():
        return render_prettyprint('api/result.html', ucoin.hdc.amendments.Promoted().get())

    @app.route('/api/hdc/amendments/promoted/<int:amendment_number>')
    def hdc_amendments_promoted_am(amendment_number):
        return render_prettyprint('api/result.html', ucoin.hdc.amendments.Promoted(amendment_number).get())

    @app.route('/api/hdc/amendments/view/<amendment_id>/members')
    def hdc_amendments_view_am_members(amendment_id):
        return render_prettyprint('api/result.html', list(ucoin.hdc.amendments.views.Members(amendment_id).get()))

    @app.route('/api/hdc/amendments/view/<amendment_id>/self')
    def hdc_amendments_view_am_self(amendment_id):
        return render_prettyprint('api/result.html', ucoin.hdc.amendments.views.Self(amendment_id).get())

    @app.route('/api/hdc/amendments/view/<amendment_id>/voters')
    def hdc_amendments_view_am_voters(amendment_id):
        return render_prettyprint('api/result.html', list(ucoin.hdc.amendments.views.Voters(amendment_id).get()))

    @app.route('/api/hdc/amendments/view/<amendment_id>/signatures')
    def hdc_amendments_view_am_signatures(amendment_id):
        return render_prettyprint('api/result.html', list(ucoin.hdc.amendments.views.Signatures(amendment_id).get()))

    @app.route('/api/hdc/amendments/votes', methods=['GET', 'POST'])
    def hdc_amendments_votes():
        if request.method == 'GET':
            return render_prettyprint('api/result.html', ucoin.hdc.amendments.Votes().get())

        amendment = request.form.get('amendment')
        signature = request.form.get('signature')
        peer = request.form.get('peer')

        return render_prettyprint('api/result.html', ucoin.hdc.amendments.Votes().post(amendment=amendment, signature=signature, peer=peer))

    @app.route('/api/hdc/amendments/votes/<amendment_id>')
    def hdc_amendments_votes_am(amendment_id):
        return render_prettyprint('api/result.html', list(ucoin.hdc.amendments.Votes(amendment_id).get()))

    @app.route('/api/hdc/coins/<pgp_fingerprint>/list')
    def hdc_coins_pgp_list(pgp_fingerprint):
        return render_prettyprint('api/result.html', ucoin.hdc.coins.List(pgp_fingerprint).get())

    @app.route('/api/hdc/coins/<pgp_fingerprint>/view/<int:coin_number>')
    def hdc_coins_pgp_view_coin(pgp_fingerprint):
        return render_prettyprint('api/result.html', ucoin.hdc.coins.List(pgp_fingerprint, coin_number).get())

    @app.route('/api/hdc/coins/<pgp_fingerprint>/view/<int:coin_number>/history')
    def hdc_coins_pgp_view_coin_history(pgp_fingerprint):
        return render_prettyprint('api/result.html', ucoin.hdc.coins.view.History(pgp_fingerprint, coin_number).get())

    @app.route('/api/hdc/transactions/process', methods=['POST',])
    def hdc_transactions_process():
        transaction = request.form.get('transaction')
        signature = request.form.get('signature')

        return render_prettyprint('api/result.html', ucoin.hdc.transactions.Process().post(transaction=transaction, signature=signature))

    @app.route('/api/hdc/transactions/all')
    def hdc_transactions_all():
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.All().get()))

    @app.route('/api/hdc/transactions/keys')
    def hdc_transactions_keys():
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.Keys().get()))

    @app.route('/api/hdc/transactions/last')
    def hdc_transactions_last():
        return render_prettyprint('api/result.html', ucoin.hdc.transactions.Last().get())

    @app.route('/api/hdc/transactions/last/<int:count>')
    def hdc_transactions_last_count(count):
        return render_prettyprint('api/result.html', ucoin.hdc.transactions.Last(count).get())

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>')
    def hdc_transactions_sender_pgp(pgp_fingerprint):
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.Sender(pgp_fingerprint).get()))

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>/last')
    def hdc_transactions_sender_pgp_last(pgp_fingerprint):
        return render_prettyprint('api/result.html', ucoin.hdc.transactions.sender.Last(pgp_fingerprint).get())

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>/last/<int:count>')
    def hdc_transactions_sender_pgp_last_count(pgp_fingerprint, count):
        return render_prettyprint('api/result.html', ucoin.hdc.transactions.sender.Last(pgp_fingerprint, count).get())

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>/transfer')
    def hdc_transactions_sender_pgp_transfer(pgp_fingerprint):
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.sender.Transfer(pgp_fingerprint).get()))

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>/issuance')
    def hdc_transactions_sender_pgp_issuance(pgp_fingerprint):
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.sender.Issuance(pgp_fingerprint).get()))

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>/issuance/last')
    def hdc_transactions_sender_pgp_issuance_last(pgp_fingerprint):
        return render_prettyprint('api/result.html', ucoin.hdc.transactions.sender.issuance.Last(pgp_fingerprint).get())

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>/issuance/fusion')
    def hdc_transactions_sender_pgp_issuance_fusion(pgp_fingerprint):
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.sender.issuance.Fusion(pgp_fingerprint).get()))

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>/issuance/dividend')
    def hdc_transactions_sender_pgp_issuance_dividend(pgp_fingerprint):
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.sender.issuance.Dividend(pgp_fingerprint).get()))

    @app.route('/api/hdc/transactions/sender/<pgp_fingerprint>/issuance/dividend/<int:amendment_number>')
    def hdc_transactions_sender_pgp_issuance_dividend_am(pgp_fingerprint, amendment_number):
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.sender.issuance.Dividend(pgp_fingerprint, amendment_number).get()))

    @app.route('/api/hdc/transactions/recipient/<pgp_fingerprint>')
    def hdc_transactions_recipient_pgp(pgp_fingerprint):
        return render_prettyprint('api/result.html', list(ucoin.hdc.transactions.Recipient(pgp_fingerprint).get()))

    @app.route('/api/hdc/transactions/view/<transaction_id>')
    def hdc_transactions_view_tx(transaction_id):
        return render_prettyprint('api/result.html', ucoin.hdc.transactions.View(transaction_id).get())
