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
from merkle import Merkle
from flask import\
    Flask, request, render_template,\
    jsonify, redirect, abort, url_for,\
    flash
from io import StringIO
from werkzeug.contrib.cache import SimpleCache
import api, wallets

logger = logging.getLogger("cli")

if __name__ == '__main__':
    app = Flask(__name__)
    app.secret_key = 'some_secret'
    cache = SimpleCache()

    api.register(app)
    wallets.register(app, cache)

    common_options = {'formatter_class': argparse.ArgumentDefaultsHelpFormatter}

    parser = argparse.ArgumentParser(description='uCoin webclient.', **common_options)

    levels = OrderedDict([('debug', logging.DEBUG),
                          ('info', logging.INFO),
                          ('warning', logging.WARNING),
                          ('error', logging.ERROR),
                          ('quiet', logging.CRITICAL),])

    parser.add_argument('--verbose', '-v', choices=[x for x in levels.keys()], default='error', help='set a verbosity level')
    parser.add_argument('--levels', '-l', action='store_true', default=False, help='list all the verbosity levels')
    parser.add_argument('--output', '-o', help='all the logging messages are redirected to the specified filename.')
    parser.add_argument('--debug', '-d', action='store_const', const='debug', dest='verbose', help='Display all the messages.')
    parser.add_argument('--info', '-i', action='store_const', const='info', dest='verbose', help='Display the info messages.')
    parser.add_argument('--warning', '-w', action='store_const', const='warning', dest='verbose', help='Only display the warning and error messages.')
    parser.add_argument('--error', '-e', action='store_const', const='error', dest='verbose', help='Only display the error messages')
    parser.add_argument('--quiet', '-q', action='store_const', const='quiet', dest='verbose', help='Quiet level of verbosity only displaying the critical error messages.')

    parser.add_argument('--user', '-u', help='PGP key to use for signature')
    parser.add_argument('--server', '-s', help='uCoin server to look data in', default='localhost')
    parser.add_argument('--port', '-p', help='uCoin server port', type=int, default=8081)

    parser.add_argument('--config', '-c', help='set a config file', default='config/config.json')

    subparsers = parser.add_subparsers(help='sub-command help')

    def run():
        print('Running...')
        app.secret_key = ucoin.settings['secret_key']
        if ucoin.settings['browser']:
            webbrowser.open('http://localhost:5000/')
        app.run(debug=True)

    sp = subparsers.add_parser('run', help='Run the webclient', **common_options)
    sp.add_argument('--secret_key', '-s', help='Pass a secret key used by the server for sessions', default='some_secret')
    sp.add_argument('--browser', '-b', action='store_true', help='Open it into your favorite browser', default=False)
    sp.set_defaults(func=run)

    args = parser.parse_args()

    if args.levels:
        print("Here's the verbose levels available:")
        for keys in levels.keys():
            print("\t", keys)
        sys.exit()

    if (args.output):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            filename=args.output, filemode='a'
            )
    else:
        logging.basicConfig(
            level=levels.get(args.verbose, logging.NOTSET),
            format='%(name)-12s: %(levelname)-8s %(message)s'
        )

    ucoin.settings.update(args.__dict__)

    try:
        with open(args.config) as f:
            ucoin.settings.update(json.load(f))
    except FileNotFoundError:
        pass

    if ucoin.settings.get('user'):
        logger.debug('selected keyid: %s' % ucoin.settings['user'])
        ucoin.settings['gpg'] = gpg = gnupg.GPG(options=['-u %s' % ucoin.settings['user']])

        secret_keys = gpg.list_keys(True)
        public_keys = gpg.list_keys()

        for idx, fp in enumerate(secret_keys.fingerprints):
            if fp[-8:] == ucoin.settings['user']:
                ucoin.settings.update(secret_keys[idx])
                break

        ucoin.settings['secret_keys'] = __secret_keys = {}
        ucoin.settings['public_keys'] = __public_keys = {}

        for k in secret_keys: __secret_keys[k['fingerprint']] = k
        for k in public_keys: __public_keys[k['fingerprint']] = k
    else:
        ucoin.settings['gpg'] = gpg = gnupg.GPG()

    ucoin.settings.update(ucoin.ucg.Peering().get())

    logger.debug(args)
    logger.debug(ucoin.settings)

    if 'func' not in args:
        parser.print_help()
        sys.exit()

    args.func()
