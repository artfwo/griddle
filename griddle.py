#! /usr/bin/env python
# -*- coding: utf-8 -*-

import liblo, sys
from liblo import *

import select, pybonjour
from pybonjour import DNSServiceBrowse
REGTYPE = "_monome-osc._udp"
devices = set()

def fixhex(s):
    return s.replace("\\032", " ").replace("\\040", "(").replace("\\041", ")")

class Bonjourish:
    def poll(self):
        ready = select.select([self.sdRef], [], [], 0)
        if self.sdRef in ready[0]:
            pybonjour.DNSServiceProcessResult(self.sdRef)
    
    def close(self):
        self.sdRef.close()

class Waffle(ServerThread):
    def __init__(self, port, devices=[]):
        ServerThread.__init__(self, port)
        self.prefix = "rove"
        self.devices = devices

    @make_method("/sys/port", "i")
    def sys_port(self, path, args):
        print "PORT", args
    
    @make_method("/sys/prefix", "s")
    def sys_prefix(self, path, args):
        prefix, = args
        self.unregister_sysmethods(self.prefix)
        self.prefix = prefix
        self.register_sysmethods(self.prefix)

    def register_sysmethods(self, prefix):
        print "registering methods"
        self.add_method("/%s/grid/led/set" % prefix, "iii", self.grid_led_set)
        self.add_method("/%s/grid/led/map" % prefix, None, self.grid_led_map)
    
    def unregister_sysmethods(self, prefix):
        print "unregistering methods"
        self.del_method("/%s/grid/led/set" % prefix, "iii")
        self.del_method("/%s/grid/led/map" % prefix, None)

    def grid_led_set(self, path, args):
        x, y, s = args
        for d in devices:
            print ">>>>>>>>>>>>>> sending to", d
            target = liblo.Address(d)
            #liblo.send(target, "/sys/prefix", "/box")
            liblo.send(target, "/box/grid/led/set", x, y, s)
            print d, "/box/grid/led/set", x, y, s
    
    def grid_led_map(self, path, values, *args):
        #x, y, s = args
        m = liblo.Message("/box/grid/led/map")
        for v in values:
            # print v,
            m.add(v)
        #print args
        for d in devices:
            #print ">>>>>>>>>>>>>> sending to", d
            target = liblo.Address(d)
            #liblo.send(target, "/sys/prefix", "/box")
            liblo.send(target, m)
            #print d, "/box/grid/led/map", args

class WaffleWrapper(Bonjourish):
    def __init__(self, devices=[]):
        self.sdRef = pybonjour.DNSServiceRegister(name = "waffle",
             regtype = "_monome-osc._udp",
             port = 20000,
             callBack = self.register_callback)

    def register_callback(self, sdRef, flags, errorCode, name, regtype, domain):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            #print 'Registered service:', name, regtype, domain
            self.waffle = Waffle(20000)
            self.waffle.start()

class Griddle(Bonjourish):
    def __init__(self):
        self.resolved = []
        self.sdRef = DNSServiceBrowse(regtype="_monome-osc._udp", callBack=self.browse_callback)
    
    def resolve_callback(self, sdRef, flags, interfaceIndex, errorCode, fullname, hosttarget, port, txtRecord):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            print ">>>>>> Resolved", fixhex(fullname), hosttarget, port, txtRecord
            devices.add(port)
            devices.discard(20000)
            print devices
            self.resolved.append(True)
    
    def browse_callback(self, sdRef, flags, interfaceIndex, errorCode, serviceName, regtype, replyDomain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return

        if not (flags & pybonjour.kDNSServiceFlagsAdd):
            print 'Service removed', serviceName
            return
        
        resolve_sdRef = pybonjour.DNSServiceResolve(0,
            interfaceIndex,
            serviceName,
            regtype,
            replyDomain,
            self.resolve_callback)

        try:
            while not self.resolved:
                ready = select.select([resolve_sdRef], [], [], 5)
                if resolve_sdRef not in ready[0]:
                    print 'Resolve timed out'
                    break
                pybonjour.DNSServiceProcessResult(resolve_sdRef)
            else:
                self.resolved.pop()
        finally:
            resolve_sdRef.close()

s = WaffleWrapper()
w = Griddle()

try:
    try:
        while True:
            import time
            s.poll()
            w.poll()
            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
finally:
    print "cleaning up..."
    s.close()
    w.close()
