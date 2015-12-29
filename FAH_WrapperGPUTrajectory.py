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
# /var/lib/fahclient/work/<wu>/01/viewerTop.json        for the atoms
# /var/lib/fahclient/work/<wu>/01/viewerFrame1.json     for the coordinates
# /var/lib/fahclient/work/<wu>/01/system.xml            for the bonds
#
# following frames might be delivered later; just as a starter
#
# Change History
#
# 2014/10/14    1.0     initial version
# 2014/10/14    1.1     removed some leftover from original purpose of the template
#                       (cnt % 100 and log of client list)
# 2015/12/23    1.2     make it a real wrapper with the goal to work with the official viewer
#                       the wrapper will intercept all traffic from the API-client to FAHClient
#                       and modify those messages related to trajectories
# 2015/12/24    1.3     issue #2: fixed hardcoded location of folder (slot vs. unit)
#                       issue #4: only one frame with positions is send back
#                       issue #5: radius of atoms are not set correctly
#                       additional: replace prints with proper logging to increase version independance
# 2015/12/29    2.0     Fix the Python 3.4 incompatibility
#                       improve error handler for pressing Control-C to terminate
#                       learn the data path from settings
#                       get the hostname from sockets
# 2015/12/29    2.1     remove logging for routing commands (mainly to avoid leakage of auth-password)
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
import logging
import glob
import platform

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
# FAHViewer --connect=<hostname>:36331 --password=<password> --slot=1
#
#

# where this wrapper is running
hostnameWrapper = ""
portWrapper = 36331

# where the FAHClient is running
hostnameClient = "localhost"
portClient = 36330

# the working path (will be read from config settings later)
workingPath = ""

atomList = []
bondList = []

atomCatalog = []

mapFSWU = {}

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


def printcopyrightandusage():
    """ (c) Christian Lohmann, 2015, FAH_WrapperGPUTrajectory"""

    LOG_FILENAME = 'fah_wrapgpu.log'

    logging.basicConfig(format='%(asctime)s:%(message)s', datefmt='%Y-%m-%d:%I:%M:%S',
#      filename=LOG_FILENAME,
      level=logging.DEBUG)

    logging.warning("******************************************************************")
    logging.warning("* (c) Christian Lohmann, 2015                                    *")
    logging.warning("* FAH_WrapperGPUTrajectory v2.1                                  *")
    logging.warning("******************************************************************")
    logging.warning("")
    logging.warning("running Python %s", platform.python_version())

    logging.info("start GPU wrapper on host %s port %d", hostnameWrapper, portWrapper)
    logging.info("connecting to FAHClient on host %s port %d", hostnameClient, portClient)

    sys.stdout.flush()


#
# sendFileThroughSocket
# Parameter:    fn      Filename with full path
#               s       Socket
#
# copy a file "as-is" trough the socket, in 1024 chunk of bytes
#
def sendFileThroughSocket(fn, s):
    """ sendFileThroughSocket """
    #logging.info("send file %s to socket %s", fn, s.getsockname())
    fh = open(fn,'rb')      # open in read/binary
    l = 1024
    while (l == 1024):
        b = fh.read(1024)
        l = len(b)
        s.send(b)

    fh.close()

#
#
def buildAtomRepository():
    """ buildAtomRepository """
    atomCatalog.append(Atom("X",  0.0, 1.50,   0.00,   0))
    atomCatalog.append(Atom("H",  0.0, 1.20,   1.08,   1))
    atomCatalog.append(Atom("He", 0.0, 1.40,   4.00,   2))
    atomCatalog.append(Atom("Li", 0.0, 1.82,   6.94,   3))
    atomCatalog.append(Atom("Be", 0.0, 2.00,   9.01,   4))
    atomCatalog.append(Atom("B",  0.0, 2.00,  10.81,   5))
    atomCatalog.append(Atom("C",  0.0, 1.70,  12.01,   6))
    atomCatalog.append(Atom("N",  0.0, 1.55,  14.01,   7))
    atomCatalog.append(Atom("O",  0.0, 1.52,  15.99,   8))
    atomCatalog.append(Atom("F",  0.0, 1.47,  18.99,   9))
    atomCatalog.append(Atom("Ne", 0.0, 1.54,  20.18,  10))
    atomCatalog.append(Atom("Na", 0.0, 1.36,  22.99,  11))
    atomCatalog.append(Atom("Mg", 0.0, 1.18,  24.31,  12))
    atomCatalog.append(Atom("Al", 0.0, 2.00,  26.98,  13))
    atomCatalog.append(Atom("Si", 0.0, 2.10,  28.09,  14))
    atomCatalog.append(Atom("P" , 0.0, 1.80,  30.97,  15))
    atomCatalog.append(Atom("S",  0.0, 1.80,  32.07,  16))
    atomCatalog.append(Atom("Cl", 0.0, 2.27,  35.45,  17))
    atomCatalog.append(Atom("Ar", 0.0, 1.88,  39.95,  18))
    atomCatalog.append(Atom("K",  0.0, 1.76,  39.10,  19))
    atomCatalog.append(Atom("Ca", 0.0, 1.37,  40.08,  20))
    atomCatalog.append(Atom("Sc", 0.0, 2.00,  44.96,  21))
    atomCatalog.append(Atom("Ti", 0.0, 2.00,  47.87,  22))
    atomCatalog.append(Atom("V",  0.0, 2.00,  50.94,  23))
    atomCatalog.append(Atom("Cr", 0.0, 2.00,  51.99,  24))
    atomCatalog.append(Atom("Mn", 0.0, 2.00,  54.94,  25))
    atomCatalog.append(Atom("Fe", 0.0, 2.00,  55.85,  26))
    atomCatalog.append(Atom("Co", 0.0, 2.00,  58.93,  27))
    atomCatalog.append(Atom("Ni", 0.0, 1.63,  58.69,  28))
    atomCatalog.append(Atom("Cu", 0.0, 1.40,  63.55,  29))
    atomCatalog.append(Atom("Zn", 0.0, 1.39,  65.41,  30))
    atomCatalog.append(Atom("Ga", 0.0, 1.07,  69.72,  31))
    atomCatalog.append(Atom("Ge", 0.0, 2.00,  72.64,  32))
    atomCatalog.append(Atom("As", 0.0, 1.85,  74.92,  33))
    atomCatalog.append(Atom("Se", 0.0, 1.90,  78.96,  34))
    atomCatalog.append(Atom("Br", 0.0, 1.85,  79.90,  35))
    atomCatalog.append(Atom("Kr", 0.0, 2.02,  83.79,  36))
    atomCatalog.append(Atom("Rb", 0.0, 2.00,  85.47,  37))
    atomCatalog.append(Atom("Sr", 0.0, 2.00,  87.62,  38))
    atomCatalog.append(Atom("Y",  0.0, 2.00,  88.91,  39))
    atomCatalog.append(Atom("Zr", 0.0, 2.00,  91.22,  40))
    atomCatalog.append(Atom("Nb", 0.0, 2.00,  92.91,  41))
    atomCatalog.append(Atom("Mo", 0.0, 2.00,  95.94,  42))
    atomCatalog.append(Atom("Tc", 0.0, 2.00,  98.00,  43))
    atomCatalog.append(Atom("Ru", 0.0, 2.00, 101.07,  44))
    atomCatalog.append(Atom("Rh", 0.0, 2.00, 102.91,  45))
    atomCatalog.append(Atom("Pd", 0.0, 1.63, 106.42,  46))
    atomCatalog.append(Atom("Ag", 0.0, 1.72, 107.87,  47))
    atomCatalog.append(Atom("Cd", 0.0, 1.58, 112.41,  48))
    atomCatalog.append(Atom("In", 0.0, 1.93, 114.82,  49))
    atomCatalog.append(Atom("Sn", 0.0, 2.17, 118.71,  50))
    atomCatalog.append(Atom("Sb", 0.0, 2.00, 121.76,  51))
    atomCatalog.append(Atom("Te", 0.0, 2.06, 127.60,  52))
    atomCatalog.append(Atom("I",  0.0, 1.98, 126.90,  53))
    atomCatalog.append(Atom("Xe", 0.0, 2.16, 131.29,  54))
    atomCatalog.append(Atom("Cs", 0.0, 2.10, 132.91,  55))
    atomCatalog.append(Atom("Ba", 0.0, 2.00, 137.38,  56))
    atomCatalog.append(Atom("La", 0.0, 2.00, 138.91,  57))
    atomCatalog.append(Atom("Ce", 0.0, 2.00, 140.12,  58))
    atomCatalog.append(Atom("Pr", 0.0, 2.00, 140.91,  59))
    atomCatalog.append(Atom("Nd", 0.0, 2.00, 144.24,  60))
    atomCatalog.append(Atom("Pm", 0.0, 2.00, 145.00,  61))
    atomCatalog.append(Atom("Sm", 0.0, 2.00, 150.36,  62))
    atomCatalog.append(Atom("Eu", 0.0, 2.00, 151.96,  63))
    atomCatalog.append(Atom("Gd", 0.0, 2.00, 157.25,  64))
    atomCatalog.append(Atom("Tb", 0.0, 2.00, 158.93,  65))
    atomCatalog.append(Atom("Dy", 0.0, 2.00, 162.50,  66))
    atomCatalog.append(Atom("Ho", 0.0, 2.00, 164.93,  67))
    atomCatalog.append(Atom("Er", 0.0, 2.00, 167.26,  68))
    atomCatalog.append(Atom("Tm", 0.0, 2.00, 168.93,  69))
    atomCatalog.append(Atom("Yb", 0.0, 2.00, 173.04,  70))
    atomCatalog.append(Atom("Lu", 0.0, 2.00, 174.97,  71))
    atomCatalog.append(Atom("Hf", 0.0, 2.00, 178.49,  72))
    atomCatalog.append(Atom("Ta", 0.0, 2.00, 180.95,  73))
    atomCatalog.append(Atom("W",  0.0, 2.00, 183.84,  74))
    atomCatalog.append(Atom("Re", 0.0, 2.00, 186.21,  75))
    atomCatalog.append(Atom("Os", 0.0, 2.00, 190.23,  76))
    atomCatalog.append(Atom("Ir", 0.0, 2.00, 192.22,  77))
    atomCatalog.append(Atom("Pt", 0.0, 1.72, 195.08,  78))
    atomCatalog.append(Atom("Au", 0.0, 1.66, 196.97,  79))
    atomCatalog.append(Atom("Hg", 0.0, 1.55, 200.59,  80))
    atomCatalog.append(Atom("Tl", 0.0, 1.96, 204.38,  81))
    atomCatalog.append(Atom("Pb", 0.0, 2.02, 207.20,  82))
    atomCatalog.append(Atom("Bi", 0.0, 2.00, 208.98,  83))
    atomCatalog.append(Atom("Po", 0.0, 2.00, 209.00,  84))
    atomCatalog.append(Atom("At", 0.0, 2.00, 210.00,  85))
    atomCatalog.append(Atom("Rn", 0.0, 2.00, 222.00,  86))
    atomCatalog.append(Atom("Fr", 0.0, 2.00, 223.00,  87))
    atomCatalog.append(Atom("Ra", 0.0, 2.00, 226.00,  88))
    atomCatalog.append(Atom("Ac", 0.0, 2.00, 227.00,  89))
    atomCatalog.append(Atom("Th", 0.0, 2.00, 232.04,  90))
    atomCatalog.append(Atom("Pa", 0.0, 2.00, 231.04,  91))
    atomCatalog.append(Atom("U",  0.0, 1.86, 238.03,  92))
    atomCatalog.append(Atom("Np", 0.0, 2.00, 237.00,  93))
    atomCatalog.append(Atom("Pu", 0.0, 2.00, 244.00,  94))
    atomCatalog.append(Atom("Am", 0.0, 2.00, 243.00,  95))
    atomCatalog.append(Atom("Cm", 0.0, 2.00, 247.00,  96))
    atomCatalog.append(Atom("Bk", 0.0, 2.00, 247.00,  97))
    atomCatalog.append(Atom("Cf", 0.0, 2.00, 251.00,  98))
    atomCatalog.append(Atom("Es", 0.0, 2.00, 252.00,  99))
    atomCatalog.append(Atom("Fm", 0.0, 2.00, 257.00, 100))
    atomCatalog.append(Atom("Md", 0.0, 2.00, 258.00, 101))
    atomCatalog.append(Atom("No", 0.0, 2.00, 259.00, 102))
    atomCatalog.append(Atom("Lr", 0.0, 2.00, 262.00, 103))
    atomCatalog.append(Atom("Rf", 0.0, 2.00, 261.00, 104))
    atomCatalog.append(Atom("Db", 0.0, 2.00, 262.00, 105))
    atomCatalog.append(Atom("Sg", 0.0, 2.00, 266.00, 106))
    atomCatalog.append(Atom("Bh", 0.0, 2.00, 264.00, 107))
    atomCatalog.append(Atom("Hs", 0.0, 2.00, 269.00, 108))
    atomCatalog.append(Atom("Mt", 0.0, 2.00, 268.00, 109))
    atomCatalog.append(Atom("Ds", 0.0, 2.00, 271.00, 110))
    atomCatalog.append(Atom("Rg", 0.0, 2.00, 272.00, 111))

#
# getCorrectAtomsData
# Parameter:    fn      Filename with full path
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
        atomTemp = atomCatalog[atomLine[4]]
        atom = Atom(atomLine[0], atomLine[1], atomLine[2], atomLine[3], atomLine[4])

        if atom.symbol == "UNKNOWN":
            atom.symbol = atomTemp.symbol
        if atom.charge == 0:
            atom.charge = atomTemp.charge
        if atom.radius == 0:
            atom.radius = atomTemp.radius
        if atom.mass == 0:
            atom.mass = atomTemp.mass

        atomList.append(atom)

    # ignore all the bonds
    # for atomLine in data["bonds"]:

    json_data.close()

#
# identifyCA
# Parameter:    none
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
# Proline makes a problem with this logic; but we don't need it anyway too much here, so keep it for later
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
                    flagAtom1 = False           # can't be Alpha Carbon
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
                    flagAtom2 = False           # can't be Alpha Carbon
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
# Parameter:    s   Stream to send the PyON message
#
# send the corrected atom data to the stream requested the trajectory
#
# radius taken from http://www.sciencegeek.net/tables/AtomicRadius.pdf
#
def sendCorrectAtomsData(st):

    sep = ""
    for atom in atomList:
        l = sep + "[\"" + atom.symbol + "\","+ str(atom.charge) +","+ str(atom.radius) +","+ str(atom.mass) +"," + str(atom.number) +"]\n"
        st.send(l.encode())
        sep = ","


#
# getCorrectBondsData
# Parameter:    fn          Filename with full path
#               maxindex    Number of atoms we are interested in
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
# Parameter:    st      Stream to send the bond list to
#
# Send the collective bonds from system.xml to the requesting stream
#
def sendCorrectBondsData(st):
    l = ""

    # get all the bonds
    cntMax = len(bondList)

    bondLast = bondList.pop(-1)     # get the last item off the list

    # get all remaining bonds out into the stream
    for bond in bondList:
        l = "[" + str(bond.atom1) + "," + str(bond.atom2) + "],"
        st.send(l.encode())

    # get the remove last bonds out into the stream; just without colon
    l = "[" + str(bondLast.atom1) + "," + str(bondLast.atom2) + "]"
    st.send(l.encode())


#
# getTrajectory(st, wu)
# Parameter:    st      Stream requesting the trajectory
#               wu      Workunit
#
# This is the main routine to get the requested trajectory of a workunit
# by reading its working folder
#
#
def getTrajectory(st, wu):
    parts = wu.split()

    logging.warn("get trajectory")

    if parts[0] == "updates" and parts[1] == "add":
        # a bit cheating now; we don't periodically perform it; but just once
        slot = parts[5]
    elif parts[0] == "trajectory":
        slot = parts[1]
    else:
        logging.error("no valid trigger for trajectory %s", parts)
        return

    slot = re.sub(r'[^\d]+', '', slot).zfill(2)

    # get the slot/WU mapping done
    WU = mapFSWU.get(slot, None)
    if WU is None:
        logging.error("no mapping done for slot %s\n%s", slot, mapFSWU)
        return

    logging.info("get trajectory for slot %s with WU %s", slot, WU)
    pn = os.path.join(workingPath, "work", WU, "01")


    logging.info("working folder %s", pn)
    if not os.path.isfile(os.path.join(pn, "viewerFrame1.json")):
        st.send("\nPyON 1 topology\n".encode())
        st.send("{\n".encode())
        st.send("\"atoms\": [],\n".encode())
        st.send("\"bonds\": []\n".encode())
        st.send("}\n".encode())
        st.send("\n---".encode())
        logging.error("no position yet known, send empty data")
        return



    getCorrectAtomsData(os.path.join(pn, "viewerTop.json"))
    maxIndex = len(atomList)
    getCorrectBondsData(os.path.join(pn, "system.xml"), maxIndex)

    identifyCA()

    logging.info("number of atoms %d", len(atomList))
    logging.info("number of bonds %d", len(bondList))

    st.send("\nPyON 1 topology\n".encode())
    st.send("{\n".encode())
    st.send("\"atoms\": [\n".encode())
    sendCorrectAtomsData(st)
    st.send("\n],\n".encode())
    st.send("\"bonds\": [".encode())
    sendCorrectBondsData(st)
    st.send("]\n".encode())
    st.send("}\n".encode())
    st.send("\n---".encode())

    #
    # loop over all files we have with position information
    #
    # oh man, I'm too lazy for this and ask for the files in two steps
    # 1) for those with only 1 digit
    fa = sorted(glob.glob(os.path.join(pn, 'viewerFrame?.json')))
    for posfile in fa:
        # just copy the viewerFrame[n].json file here; structure fits; content is ok
        st.send("\nPyON 1 positions\n".encode())
        sendFileThroughSocket(posfile, st)
        st.send("\n---\n".encode())

    # 2) for those with two digits
    fa = sorted(glob.glob(os.path.join(pn, 'viewerFrame??.json')))
    for posfile in fa:
        # just copy the viewerFrame[n].json file here; structure fits; content is ok
        st.send("\nPyON 1 positions\n".encode())
        sendFileThroughSocket(posfile, st)
        st.send("\n---\n".encode())


    # cleanup to avoid double sending with next request
    del atomList[:]
    del bondList[:]
    del fa



def FAHMM_Wrapper_GPU_Trajectory(hnW, portWrapper, hnC, portClient):

    backlog = 5
    size = 1024*16

    global workingPath

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

    logging.info("Trajectory server created with socket %s", sockTrajectory.getsockname())
    logging.info("Trajectory client created with socket %s", sockClient.getsockname())

    cnt = 1
    running = 1

    while running:

        # error handler for the select.select
        try:
            ready_to_read, ready_to_write, in_error = \
                  select.select(input, output, [])
            #logging.debug("%d: entries in rq %d wq %d error %d", cnt, len(ready_to_read), \
            #                       len(ready_to_write), \
            #                       len(in_error)
        except IOError as e:
            logging.error("select %s", e)
            if e.errno == 9:
                break
        except (KeyboardInterrupt, SystemExit):
            logging.error("wrapper to end as per keyboard or signal")
            running = 0
        except:
            logging.error("select, unexpected error %s", sys.exc_info()[0])
            logging.error("backtrace\n%s", sys.exc_traceback.tb_lineno)
            raise

        cnt = cnt + 1

        try:
            for s in ready_to_read:

                if s is sockTrajectory:
                    # logging.debug("trajectory socket %s", s.getsockname())
                    # a new client want to connect
                    client, adress = sockTrajectory.accept()
                    if client is not None:
                        for c in clientList:
                            logging.warning("forced close active connection(s), only one client is allowed per host %s", c)
                            input.remove(c)
                            clientList.remove(c)
                            c.shutdown(socket.SHUT_RDWR)
                            c.close()

                        input.append(client)
                        clientList.append(client)
                        logging.warning("new connection for %s established", adress)
                elif s is sockClient:
                    clientData = sockClient.recv(size).decode()
                    if len(clientData) > 0:
                        for c in clientList:
                            #logging.info("response %s", clientData)
                            c.send(clientData.encode())

                        # build the mapping table for slot/work units
                        startTag = "PyON 1 units\n"
                        startPos = clientData.find(startTag)
                        if startPos >= 0:
                            startPos = startPos + len(startTag)
                            endPos = clientData.find("\n---", startPos)
                        else:
                            endPos = -1

                        if startPos >= 0 and endPos >= startPos:
                            infoText = clientData[startPos:endPos]
                            qi = json.loads(infoText)

                            # get all slot/unit maps
                            for qia in qi:
                                mapFSWU[qia['slot']] = qia['id']

                            logging.info("map %s", mapFSWU)

                        #
                        # build the mapping table for slot/work units
                        startTag = "PyON 1 info\n"
                        startPos = clientData.find(startTag)
                        if startPos >= 0:
                            startPos = startPos + len(startTag)
                            endPos = clientData.find("\n---", startPos)
                        else:
                            endPos = -1

                        if startPos >= 0 and endPos >= startPos:
                            infoText = clientData[startPos:endPos]
                            qi = json.loads(infoText)

                            # get the "System" part of the list
                            for qis in qi:
                                qin = qis.pop(0)
                                if qin == "System":
                                    for qit in qis:
                                        if qit[0] == "CWD":
                                            workingPath = qit[1]
                                            logging.info("working folder from config %s", workingPath)

                elif s is sys.stdin:
                    junk = sys.stdin.readline()
                    while len(clientList) > 0:
                        c  = clientList[0]
                        logging.info("close connection by user, FAH client %s is gone", c)
                        input.remove(c)
                        clientList.remove(c)
                        c.shutdown(socket.SHUT_RDWR)
                        c.close()
                    running = 0
                    break
                else:
                    # logging.debug("regular socket %s", s.getsockname())
                    # read a data block
                    data = s.recv(size).decode()
                    if data:
                        # logging.info("received from %s:\n%s", s, data)
                        sepline = data.splitlines(1)
                        for l in sepline:
                            # logging.debug("command: %s", l)
                            if l.startswith("exit") == True:
                                running = 0
                            elif l.startswith("traj") == True:
                                getTrajectory(clientList[0], l)
                            elif l.startswith("trajectory") == True:
                                getTrajectory(clientList[0], l)
                            elif "trajectory" in l:
                                # this one is to catch those trajectories within a scheduled event
                                getTrajectory(clientList[0], l)
                            else:
                                #logging.info("routing %s", l)
                                sockClient.send(l.encode())
                                if l.find("heartbeat") >= 0:
                                    # trigger a folder determination
                                    if workingPath == '':
                                        sockClient.send("info\n".encode())
                                    sockClient.send("queue-info\n".encode())


                    else:
                        # logging.warning("end of stream %s, remove", s)
                        s.close()
                        clientList.remove(s)
                        input.remove(s)
        except IOError as e:
            logging.error("error %s", e)
            if e.errno == 9:
                break
        except:
            logging.error("unexpected error %s", sys.exc_info()[0])
            logging.error("backtrace\n%s", sys.exc_traceback.tb_lineno)
            raise
        sys.stdout.flush()

    for c in clientList:
        logging.warning("close active connection with host %s", c)
        input.remove(c)
        clientList.remove(c)
        c.shutdown(socket.SHUT_RDWR)
        c.close()

    sockTrajectory.close()
    logging.warning("FAHMMWrapperGPUTrajectory server stopped running\n")


if __name__ == '__main__':

  if hostnameWrapper == '':
    hostnameWrapper = socket.gethostname()
  if hostnameClient == '':
    hostnameClient = socket.gethostname()

  printcopyrightandusage()
  buildAtomRepository()


  FAHMM_Wrapper_GPU_Trajectory(hostnameWrapper, portWrapper, hostnameClient, portClient)
