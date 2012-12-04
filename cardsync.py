#!/usr/bin/env python
# coding: utf-8
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at pkg/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at pkg/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#
##
# As long as the Oracle davserver will not support carddav, this script can used 
# to sync Sun/Oracle CommsSuite Addressbook to carddav server
# for continuous ondamand sync you have to activate 'retro change log plugin' on the LDAP server
# configs are stored in file cardsync.cfg, passwords are crypt with 
# >>> from Crypto.Cipher import DES
# >>> cr = DES.new('cardsync',DES.MODE_ECB)
# >>> base64.b64decode(cr.encrypt(passwd)) rpadded with space
# sample config file:
'''
[DAVICAL]
user: admin
passwd: xxxxxxxxx=
davurl: http://davical.domain.lan/caldav.php
carddavuri: %s/%s/addresses/%s.ics

[LDAP]
binddn: cn=Directory Manager
bindcred: xxxxxxxx=
ldapurl: ldap://davical.domain.lan:389
timeframe: 24
'''
# timeframe - is the time in hours for how long it will look in the past for changes
# it use vobject for handle vcard data and requests for communicate with carddavserver
# for Solaris all modules can downloaded from http://www.opencsw.org
##

import ldap
import vobject
import re
import requests
from datetime import datetime, timedelta;
from time import strptime
import ConfigParser
import getopt
import sys
from Crypto.Cipher import DES
from base64 import b64encode, b64decode

headers = {"User-Agent": "CardSync"}
headers['content-type'] = "text/vcard; charset='utf-8'"
# headers['If-None-Match'] = '*'
haveChanged = []

##
# add Email line to vcard
# @param: vc vcard
# @param: addr email address
# @param: attr type of email address
# @return: next index
def addEmail(vc,addr,attr,idx):
    vc.add('email')
    vc.email_list[idx].value = addr
    vc.email_list[idx].type_paramlist = ['INTERNET',attr.upper()]
    if idx==0:
        vc.email_list[idx].type_paramlist.append('PREF')
    return idx + 1

##
# add Telephon number line to vcard
# @param: vc vcard
# @param: no telephone number
# @param: attr type of telephone number
# @return: next index
def addTel(vc,no,attr,idx):
    vc.add('tel')
    vc.tel_list[idx].value = no.decode('utf-8')
    vc.tel_list[idx].type_param = attr.upper()
    return idx + 1

## 
# @param ldapconn LDAP connection handle
# @param dn LDAP principal which used to read the changelog and the addressbooks
# @param willChange list of modified/added entries
# @param changeTime time of modify in LDAP, will used for generate the REV line
# @param modtype create or modify, not used yet, allways add
def syncEntry(ldapconn, dn, willChange, changeTime, modtype):
    try: 
        abe = ldapconn.search_s(dn,ldap.SCOPE_BASE,'objectclass=piTypePerson')
        for dn, attr in abe:
#                        print attr
            owner = dn.split(',')[1].split('=')[1]
            entry = attr['piEntryID'][0]
            if entry not in willChange:
                willChange.append(entry)
                print carddavurl % (davurl,owner,entry)
                vc = vobject.vCard()
                gn = attr['givenName'][0] if 'givenName' in attr.keys() else ''
                sn = attr['sn'][0] if 'sn' in attr.keys() else attr['displayName'][0]
                vc.add('n')
                vc.n.value = vobject.vcard.Name(family=sn.decode('utf-8'),given=gn.decode('utf-8'))
                vc.add('fn')
                vc.fn.value = attr['displayName'][0].decode('utf-8')
                vc.add('uid')
                vc.uid.value = attr['memberOfPIBook'][0]+'-'+attr['piEntryID'][0]
                j = 0
                for i in range(3):
                    try:
                        j = addEmail(vc,attr['piEmail'+str(i+1)][0],attr['piEmail'+str(i+1)+'Type'][0],j)
                    except KeyError:
                        pass
                try:
                    d = attr['company'][0]
                    vc.add('org')
                    vc.org.value = [ attr['company'][0].decode('utf-8').replace(',','\,') ]
                except KeyError:
                    pass
                j = 0
                for i in range(6):
                    try:
                        j = addTel(vc,attr['piPhone'+str(i+1)][0],attr['piPhone'+str(i+1)+'Type'][0],j)
                    except KeyError:
                        pass
                j = 0
                try:
                    d = attr['workCity'][0]
                    vc.add('adr')
                    street = attr['workPostalAddress'][0].decode('utf-8') if 'workPostalAddress' in attr.keys() else ''
                    plz = attr['workPostalCode'][0] if 'workPostalCode' in attr.keys() else ''
                    state = attr['workState'][0].decode('utf-8') if 'workState' in attr.keys() else ''
                    country = attr['workCountry'][0].decode('utf-8') if 'workCountry' in attr.keys() else ''
                    vc.adr.value = vobject.vcard.Address(street,attr['workCity'][0].decode('utf-8'),state,plz,country,'','')
                    vc.adr.type_param = 'WORK'
                    j = 1
                except KeyError:
                    pass
                try:
                    d = attr['homeCity'][0]
                    vc.add('adr')
                    street = attr['homePostalAddress'][0].decode('utf-8') if 'homePostalAddress' in attr.keys() else ''
                    plz = attr['homePostalCode'][0] if 'homePostalCode' in attr.keys() else ''
                    state = attr['homeState'][0].decode('utf-8') if 'homeState' in attr.keys() else ''
                    country = attr['homeCountry'][0].decode('utf-8') if 'homeCountry' in attr.keys() else ''
                    vc.adr_list[j].value = vobject.vcard.Address(street,attr['homeCity'][0].decode('utf-8'),state,plz,country,'','')
                    vc.adr_list[j].type_param = 'HOME'
                except KeyError:
                    pass
                vc.add('rev')
                vc.rev.value = changeTime

                vcard=vc.serialize()  
                response = requests.put(carddavurl % (davurl,owner,entry), data=vcard, headers=headers, auth=(user, passwd))
                if (response.status_code and 200) == 200:
                    haveChanged.append(entry)
                print response.status_code
                # vc.prettyPrint()

    except ldap.NO_SUCH_OBJECT:
        print "ERROR: Not found: (%s) %s" % (modtype, dn)

##
# read the LDAP changelog and sync changes to carddav server
def syncLdapChanges():
    willChange = []
    c = ldap.initialize(ldapurl)
    c.bind(binddn,bindcred)
    changes = c.search_s('cn=changelog',ldap.SCOPE_SUBTREE,'(objectclass=changelogentry)',['targetdn','changetype','changetime'])
    for dn,clattr in changes:
        if datetime.strptime(clattr['changetime'][0],'%Y%m%d%H%M%SZ') > datetime.now() - timedelta(hours=timeframe) and clattr['changetype'][0] != 'delete':
            if  re.split('.*,',clattr['targetdn'][0])[1].lower() == 'o=piserverdb':
                syncEntry(c,clattr['targetdn'][0],willChange, clattr['changetime'][0],clattr['changetype'][0])
    
    #    print clattr['changetime'][0], clattr['changetype'][0]
    

##
# initial/total sync of users addressbook
# @param name username
def syncAll(name):
    willChange = []
    c = ldap.initialize(ldapurl)
    c.bind(binddn,bindcred)
#    print 'search: (&(objectclass=inetorgperson)(uid=%s))' % name
    entry = c.search_s('dc=contac,dc=lan',ldap.SCOPE_SUBTREE,'(&(objectclass=inetorgperson)(uid=%s))' % name,['psroot'])
    try:
        for dn,abattr in entry:
#            print re.split('.*/',abattr['psroot'][0])[1]
            try:
                abes = c.search_s(re.split('.*/',abattr['psroot'][0])[1],ldap.SCOPE_ONELEVEL,'(objectClass=PITYPEPERSON)',['modifytimestamp'])
                for dn,edn in abes:
                    print dn
                    syncEntry(c,dn,willChange,edn['modifytimestamp'][0],'create')    
            except ldap.NO_SUCH_OBJECT:
                print "No Addressbook for %s" % name

    except KeyError:
        print 'PSROOT NOT FOUND: %s?%s?&(objectclass=inetorgperson)(uid=%s))?%s' % (ldapurl,ldap.SCOPE_SUBTREE,name,['psroot'])

##
# print usage
def usage():
    hlp='''useage: cardsync.py [-i|--init <username>]|[-u|--update]
    option 'i' and 'u' are mutual exclusive
'''
    print hlp
    sys.exit( 2 )

##
# parse command line
def parseCmdlineArgs():
    try:
        opts, args = getopt.getopt( sys.argv[1:],
            "i:u", [ "init=",'update'] )
    except getopt.GetoptError:
        usage()
     
    args = {}
    args[ "init" ] = ""
    args['update'] = False

    for o, a in opts:
       if o in ("-i", "--init"):
            args[ "init" ] = a
       if o in ("-u", '--update'):
            args[ "update" ] = True

    return args

 
# read config
cf = ConfigParser.ConfigParser()
cr = DES.new('cardsync',DES.MODE_ECB)
cf.read('cardsync.cfg')
binddn    = cf.get('LDAP','binddn')
bindcred  = cr.decrypt(b64decode(cf.get('LDAP','bindcred'))).rstrip()
ldapurl   = cf.get('LDAP','ldapurl')
timeframe = int(cf.get('LDAP','timeframe'))
user      = cf.get('DAVICAL','user')
passwd  = cr.decrypt(b64decode(cf.get('DAVICAL','passwd'))).rstrip()
davurl    = cf.get('DAVICAL','davurl')
carddavurl = cf.get('DAVICAL','carddavuri')

args = parseCmdlineArgs()
if  args["init"]=='' and not args['update']:
    usage()

if args['init']:
    syncAll(args['init'])
    sys.exit(0);

if args['update']:
    syncLdapChanges()
    sys.exit(0)
    
usage()


