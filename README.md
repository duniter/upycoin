# uPyCoin (version 0.2)

uPyCoin is a webclient in order to manage your wallet based on uCoin.

## Installation

### Requirements

uPyCoin uses Python 3 so if it is not yet installed on your distribution do it and in addition you have to install pip in order to do the following steps.

Here are the python packages you should install in order to use uPyCoin thanks to pip3:

 * [python-gnupg](http://pythonhosted.org/python-gnupg/)
 * [requests](http://python-requests.org/)
 * [flask](flask.pocoo.org)

Follow the example below:

```bash
$ sudo pip3 install python-gnupg
$ sudo pip3 install requests
$ sudo pip3 install flask
```

### Submodules

You have to first get the submodules used by this git repository using the following command lines:

```bash
$ git submodule init
$ git submodule update
```

### Configuration

You should then configure a few parameters as illustrated in the following steps:

* First copy (or rename) the file config/config.json-dist to config/config.json
* Edit the new file config/config.json
* And fulfill variables as follows:
```json
{
    "server": "mycurrency.candan.fr",
    "port": 8081,
    "auth": false,
    "user": "25500A07"
}
```

### Ready to test

Once all the previous steps were done, you are then ready to launch the webclient. Use the following command line to do so:

```bash
$ ./webclient.py -i run
```

From your favorite browser, open the URL [http://localhost:5000](http://localhost:5000) and have fun!

## How does it work?

uCoin aims to help building P2P crypto-currencies based on individuals and Universal Dividend. More details on [ucoin.io](http://ucoin.io).

## Features

**Multi-wallets**

You can manage many wallets from one instance of uPyCoin.

**Transfer**

A very easy interface of transaction enables you to send coins to whatever PGP address you want. Even for people not yet subscribed on a monetary currency.

**Issuance**

When your Universal Dividend is ready to be issued to your wallet, use this feature in order to get it.

**History**

Browse through all of your transactions you sent or received.

## Change Logs

### 0.2

* replaced slidebar from transfer page by a basic text input controler since the computation complexity to get all combinations coins was too high, you can easily set the amount want to send.
* created the issuance page in order to issue your own available UD thanks to nice slidebars and a random selection of coins.
* divided both the projects ucoin-python-api and upycoin since their goals are differents.
* since the code was refactorized in ucoin-python-api use of the new design in webclient.py and client.py
* fixed a few bugs
* better explanations in README

### 0.1

* initialization of the project based on flask
* created a basic interface in order to browse through your wallets
* history page to see the transactions history for several types of transactions
* transfer page make a transfer to another account using its pgp fingerprint, a nice slidebar to select between several combinations of available coins
* fixed a few bugs
