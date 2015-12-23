#! /usr/bin/env python

#
# Author: Christian Lohmann 2014-2015
#
# a little helper script to deliver the GPU trajectories similar to the regular API
#
#
# This script is made as ad-interim solution and in hope to get deleted the day after 
# the official client/core version will be enabled to deliver the required data back 
# to requesting clients.
#
# The following files will be send back to the requester
# /var/lib/fahclient/work/<wu>/01/viewerTop.json		for the atoms
# /var/lib/fahclient/work/<wu>/01/viewerFrame1.json		for the coordinates
# /var/lib/fahclient/work/<wu>/01/system.xml			for the bonds
#
# following frames might be delivered later; just as a starter
#
# Change History
#
# 2014/10/14	1.0		initial version
# 2014/10/14	1.1		removed some leftover from original purpose of the template 
# 						(cnt % 100 and print of client list)
# 2015/12/23	1.2		make it a real wrapper with the goal to work with the official viewer
#						the wrapper will intercept all traffic from the API-client to FAHClient
#						and modify those messages related to trajectories
#
#

#
# to run the script:
#
# in test mode:
#   python FAH_WrapperGPUTrajectory.py
#
# in a background mode:
#   nohup python FAH_WrapperGPUTrajectory.py &
#
# Can be tested with a simple   "telnet <hostname> 36331"
# then enter "trajectory 01" and press enter (or whatever workunit you have with GPU)
#
# when run as console the stdin can be used to terminate the script
# when run as daemon we should add a signal handler; right now I'm to lazy for that
#

import os
import sys
import time
import datetime
import socket
import select
import string
import re
import xml.etree.ElementTree as ET
import json
import os.path

#
# Adopt here the path pointing to your working directory from FAHClient
#
# As I only have Linux I was not able to test with Windows (wouldn't even know where the path is)
# Help from Windows users is more then welcomes
#
#

#
# change here the hostnames
#

#
# right now this wrapper need to run on the same machine as the FAHClient as we need to access the files directly.
# The viewer can be on a remote machine and started like this
# FAHViewer --connect=linuxpowered:36331 --password=<password> --slot=1
#
#

# where this wrapper is running
hostnameWrapper = "linuxpowered"
portWrapper = 36331

# where the FAHClient is running
hostnameClient = "linuxpowered"
portClient = 36330

workingPath = "/var/lib/fahclient/work/"

atomList = []
bondList = []


#
# Atom-Object
#        
class Atom(object):
    def __init__(self,symbol,charge,radius,mass,number):
        self.symbol=symbol
        self.charge=0
        self.radius=0
        self.mass=0
        self.number=number
        self.atomList = []
    class __metaclass__(type):
    	def __iter__(self):
            for attr in dir(Foo):
                if not attr.startswith("__"):
                    yield attr
                            
#
# Bond-Object
#        
class Bond(object):
    def __init__(self,atom1,atom2):
        self.atom1=atom1
        self.atom2=atom2
    class __metaclass__(type):
    	def __iter__(self):
            for attr in dir(Foo):
                if not attr.startswith("__"):
                    yield attr
	
#
# sendFileThroughSocket
# Parameter:	fn		Filename with full path
#				s		Socket
#
# copy a file "as-is" trough the socket, in 1024 chunk of bytes
#
def sendFileThroughSocket(fn, s):
	print tst,"Send filename", fn, "to", s.getsockname()
	fh = open(fn,'rb') 		# open in read/binary
	l = 1024
	while (l == 1024):
		b = fh.read(1024) 
		l = len(b)
		s.send(b)

	fh.close()
	
	
#
# getCorrectAtomsData
# Parameter:	fn		Filename with full path
#
# get the atom information from viewerTop.json
# Of main interest are the symbols, radius and number; to bad radius is not prodvided
#
def getCorrectAtomsData(fn):
	json_data = open(fn, 'r')
	data = json.load(json_data)
	global atomList
	
	# read all the atoms
	for atomLine in data["atoms"]:
		atom = Atom(atomLine[0], atomLine[1], atomLine[2], atomLine[3], atomLine[4])
		atomList.append(atom)

	# ignore all the bonds
#	for atomLine in data["bonds"]:

	json_data.close()
	
#
# identifyCA
# Parameter:	none
#
# This method analyse the bonds for C-C couples to identify what the is AlphaCarbon
# as relevant information to be further used to determine the backchain and peptides 
# building a protein
#
# Atom numbers to be played with
# H: 1
# C: 6
# N: 7
# O: 8
#
def identifyCA():
	for bond in bondList:
		
		atom1 = atomList[bond.atom1]
		atom2 = atomList[bond.atom2] 
	
		# figure out if we have a couple of C-C atoms 
		if (atom1.number == 6 and atom2.number == 6):
			cntN = 0
			cntC = 0
			cntO = 0
			cntH = 0
			
			flagAtom1 = True
			flagAtom2 = True
						
			# count all bonded atoms for the first C
			for atom3 in atom1.atomList:
				if atom3.number == 1:
					cntH = cntH + 1
				if atom3.number == 6:
					cntC = cntC + 1
				if atom3.number == 7:
					cntN = cntN + 1
				if atom3.number == 8:
					flagAtom1 = False			# can't be Alpha Carbon
					cntO = cntO + 1
			
				
			# count all bonded atoms for the second C
			for atom3 in atom2.atomList:
				if atom3.number == 1:
					cntH = cntH + 1
				if atom3.number == 6:
					cntC = cntC + 1
				if atom3.number == 7:
					cntN = cntN + 1
				if atom3.number == 8:
					flagAtom2 = False			# can't be Alpha Carbon
					cntO = cntO + 1
					
			# now checking what we found: 
			# there must be exactly one "O" and two "N"; "C" and "H" have different possible counts
			# 
			#    H  O
			#    |  |
			# N--C--C--N
			#    |
			#   C?H
			#
			# Good enough for the current environment we are in ...
			#
			if cntO == 1 and cntN == 2 and (cntC == 2 or cntC == 3) and (cntH == 1 or cntH == 2):
				if flagAtom1 == False and flagAtom2 == True:
					atom2.symbol = "CA"	
				elif flagAtom2 == False and flagAtom1 == True:
					atom1.symbol = "CA"	
#
#
# sendCorrectAtomsData
# Parameter:	s	Stream to send the PyON message
#
# send the corrected atom data to the stream requested the trajectory
#
def sendCorrectAtomsData(st):

	for atom in atomList:
		if atom.number == 1: 
		  l = "[\"" + atom.symbol + "\",0,1,0," + str(atom.number) +"],\n"
		elif atom.number == 6: 
		  l = "[\"" + atom.symbol + "\",0,4,0," + str(atom.number) +"],\n"
		elif atom.number == 7: 
		  l = "[\"" + atom.symbol + "\",0,5,0," + str(atom.number) +"],\n"
		elif atom.number == 8: 
		  l = "[\"" + atom.symbol + "\",0,6,0," + str(atom.number) +"],\n"
		else: 
		  l = "[\"" + atom.symbol + "\",0,7,0," + str(atom.number) +"],\n"
		st.send(l)


#
# getCorrectBondsData
# Parameter:	fn			Filename with full path
#				maxindex	Number of atoms we are interested in 
#
# Read the full list bonds and constraints from system.xml to get the full picture. 
# As the bonds/constraints also contain all the water and other atom we have the count of 
# atoms serving as threshold to ignore those non-protein atoms
#
def getCorrectBondsData(fn, maxindex):
	data = ET.parse(fn)
	root = data.getroot()

	#
	# loop over the constraints
	#
	for bond in root.iter('Constraint'):
		p1 = int(bond.get('p1'))
		p2 = int(bond.get('p2'))
		if (p1 < maxindex and p2 < maxindex):
			bond = Bond(p1, p2)
			bondList.append(bond)
			
			atom1 = atomList[p1]
			atom2 = atomList[p2]
			atom1.atomList.append(atom2)
			atom2.atomList.append(atom1)

	#
	# loop over the bonds
	#
	for bond in root.iter('Bond'):
		p1 = int(bond.get('p1'))
		p2 = int(bond.get('p2'))
		if (p1 < maxindex and p2 < maxindex):
			bond = Bond(p1, p2)
			bondList.append(bond)
			
			atom1 = atomList[p1]
			atom2 = atomList[p2]
			atom1.atomList.append(atom2)
			atom2.atomList.append(atom1)
		
	data = []
	root = []


#
# sendCorrectBondsData
# Parameter:	st		Stream to send the bond list to
#
# Send the collective bonds from system.xml to the requesting stream
#
def sendCorrectBondsData(st):
	l = ""

	# get all the bonds
	cntMax = len(bondList)
	
	bondLast = bondList.pop(-1)		# get the last item off the list

	# get all remaining bonds out into the stream
	for bond in bondList:
		l = "[" + str(bond.atom1) + "," + str(bond.atom2) + "],"
		st.send(l)

	# get the remove last bonds out into the stream; just without colon
	l = "[" + str(bondLast.atom1) + "," + str(bondLast.atom2) + "]"
	st.send(l)


#
# getTrajectory(st, wu)
# Parameter:	st		Stream requesting the trajectory
#				wu		Workunit 
# 
# This is the main routine to get the requested trajectory of a workunit
# by reading its working folder
#
# 
def getTrajectory(st, wu):
	parts = wu.split()
	print tst,"Get trajectory for WU", parts[1]
	pn = workingPath + parts[1] + "/01/"
	pn = workingPath + "01" + "/01/"
	
	print "working files", pn

	if not os.path.isfile(pn+"viewerFrame1.json"):
		st.send("\nPyON 1 topology\n")
		st.send("{\n")
		st.send("\"atoms\": [],\n")
		st.send("\"bonds\": []\n")
		st.send("}\n")
		st.send("\n---")
		print tst,"no position yet known, send empty data"
		return

		

	getCorrectAtomsData(pn+"viewerTop.json")
	maxIndex = len(atomList)
	getCorrectBondsData(pn+"system.xml", maxIndex)
	
	identifyCA()
	
	print tst,"Number of atoms", len(atomList)
	print tst,"Number of bonds", len(bondList)
	
	st.send("\nPyON 1 topology\n")
	st.send("{\n")
	st.send("\"atoms\": [\n")
	sendCorrectAtomsData(st)
	st.send("\n],\n")
	st.send("\"bonds\": [")
	sendCorrectBondsData(st)
	st.send("]\n")
	st.send("}\n")
	st.send("\n---")

	#
	# later we can build a loop here and copy all viewerFrame<n>.json files to 
	# give the movements of the protein while folding
	#
	# just copy the viewerFrame1.json file here; structure fits; content is ok
	#

	st.send("\nPyON 1 positions\n")
	sendFileThroughSocket(pn+"viewerFrame1.json", st)
	st.send("\n---\n")


	#
	#st.send("\n>ok\n")
	
	# cleanup to avoid double sending with next request
	del atomList[:]
	del bondList[:]

	
   
def FAHMM_Wrapper_GPU_Trajectory(hnW, portWrapper, hnC, portClient):

    backlog = 5
    size = 1024*8
    
    global ts
    global tst
    
    ts = time.time()
    tst = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

    print "\n\n(c) Christian Lohmann 2014-2015"
    print "FAHMMWrapperGPUTrajectory running on host", hnW, ":", portWrapper, "and routing to", hnC,":",portClient, "\n"
    
    
	#
	# establish as trajectory server on the given host and port
	#
    sockTrajectory = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sockTrajectory.setblocking(0)
    sockTrajectory.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sockTrajectory.bind((hnW, portWrapper))
    sockTrajectory.listen(backlog)
    
    time.sleep(1)
    
	#
	# establish FAH API connection to the given host and client port
	#
    sockClient = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sockClient.connect((hnC, portClient))


    # lists of sockets
    # input = [sys.stdin, sockTrajectory]
    input = [sockTrajectory]       # when run as daemon we don't need stdin
    output = []
    clientList = []
    
    input.append(sockClient)
    output.append(sockClient)
	
    print tst,"Trajectory server created socket ", sockTrajectory.getsockname()
    print tst,"Trajectory client created socket ", sockClient.getsockname()
    
    cnt = 1
    running = 1

    while running:

        # error handler for the select.select 
        try:
            ready_to_read, ready_to_write, in_error = \
                  select.select(input, output, [])
            #print cnt, ": entries in rq", len(ready_to_read), \
            #                       " wq", len(ready_to_write), \
            #                       "error", len(in_error)
        except IOError as e:
            print tst,"select", e
            if e.errno == 9:
                break
        except:
            print tst,"select, unexpected error", sys.exc_info()[0]
            print sys.exc_traceback.tb_lineno
            raise

        cnt = cnt + 1

        try:    
            for s in ready_to_read:
            	
            	# get actual timestamp
            	ts = time.time()
            	tst = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

                if s is sockTrajectory:
                    # print "trajectory socket", s.getsockname()
                    # a new client want to connect
                    client, adress = sockTrajectory.accept()
                    if client is not None:
                        for c in clientList:
                            print tst, "forced close active connection(s), only one client is allowed per host", c
                            input.remove(c)
                            clientList.remove(c)
                            c.shutdown(socket.SHUT_RDWR)
                            c.close()
                    
                        input.append(client)
                        clientList.append(client)
                        print tst, "new connection for", adress, "established"	
                elif s is sockClient:
                   clientData = sockClient.recv(size)
                   if clientData <> '':
                     for c in clientList:
                       print "response", clientData
                       c.send(clientData)

                elif s is sys.stdin:
                    # print "stdin"
                    # close all client connections
                    junk = sys.stdin.readline()
                    while len(clientList) > 0:
                        c  = clientList[0]
                        print "close connection by user, FAH client is gone", c
                        input.remove(c)
                        clientList.remove(c)
                        c.shutdown(socket.SHUT_RDWR)
                        c.close()
                    running = 0
                    break
                else:
                    # print "regular socket", s.getsockname()
                    # read a data block
                    data = s.recv(size)
                    if data:
                        # print tst,"received from", s, ":\n", data
                        sepline = data.splitlines(1)
                        for l in sepline:
                           # print the command; without linebreak (is part of the command)
                           # print tst,"command:", l,   
                           # if l.startswith("auth"):    sockTrajectory.send(">OK\n")
#                           elif l.startswith("info"):  sockTrajectory.send(l)
                           if l.startswith("exit"):  running = 0
#                           elif l.startswith("sleep"): sockTrajectory.send(l)
                           elif l.startswith("traj"): getTrajectory(clientList[0], l) 
                           elif l.startswith("trajectory"): getTrajectory(clientList[0], l) 
                           elif "trajectory" in l: getTrajectory(clientList[0], l) 
                           else: 
                             print tst,"route", l
                             sockClient.send(l)
                    else:
                        # print "end of stream, remove", s
                        s.close()
                        clientList.remove(s)
                        input.remove(s)
        except IOError as e:
            print e
            if e.errno == 9:
                break
        except:
            print "unexpected error", sys.exc_info()[0]
            print sys.exc_traceback.tb_lineno
            raise
        sys.stdout.flush()


    sockTrajectory.close()
    print "FAHMMWrapperGPUTrajectory server stopped running\n"
    


ts = time.time()
tst = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
FAHMM_Wrapper_GPU_Trajectory(hostnameWrapper, portWrapper, hostnameClient, portClient)
