#! /usr/bin/env python
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#
# Copyright (C) 2011 Artem Popov <artfwo@gmail.com>
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

import sys, time, socket, select, pybonjour, itertools, math
from OSC import OSCClient, OSCServer, OSCMessage, NoCallbackError

REGTYPE = '_monome-osc._udp'

DEFAULT_APP_HOST = '127.0.0.1'
DEFAULT_APP_PORT = 8000
DEFAULT_APP_PREFIX = '/monome'
GRIDDLE_SERVICE_PREFIX = 'griddle'
GRIDDLE_PREFIX = '/griddle'

def fix_prefix(s):
    return '/%s' % s.strip('/')

class Waffle:
    def waffle_send_any(self, host, port, path, *args):
        msg = OSCMessage(path)
        map(msg.append, args)
        self.client.sendto(msg, (host, port), timeout=0)
    
    def waffle_send(self, path, *args):
        msg = OSCMessage(path)
        map(msg.append, args)
        self.client.send(msg)
    
    def waffle_handler(self, addr, tags, data, client_address):
        if addr.startswith(self.prefix):
            if self.app_callback:
                self.app_callback(self.id, addr.replace(self.prefix, "", 1), tags, data)
        else:
			raise NoCallbackError(addr)

# TODO: unfocus on host 
# TODO: /sys/connect
class Monome(OSCServer, Waffle):
    def __init__(self, id, address):
        OSCServer.__init__(self, ('', 0))
        self.client.connect(address)
        host, port = self.client.socket.getsockname()

        self.id = id
        self.focused = False
        self.prefix = GRIDDLE_PREFIX
        
        self.addMsgHandler('default', self.waffle_handler)
        self.addMsgHandler('/sys/info', self.sys_misc)
        self.addMsgHandler('/sys/connect', self.sys_misc)
        self.addMsgHandler('/sys/disconnect', self.sys_misc)
        self.addMsgHandler('/sys/id', self.sys_misc)
        self.addMsgHandler('/sys/size', self.sys_size)
        self.addMsgHandler('/sys/host', self.sys_host)
        self.addMsgHandler('/sys/port', self.sys_port)
        self.addMsgHandler('/sys/prefix', self.sys_prefix)
        self.addMsgHandler('/sys/rotation', self.sys_misc)
        
        self.waffle_send('/sys/host', host)
        self.waffle_send('/sys/port', port)
        self.waffle_send('/sys/info', host, self.server_address[1])
        
        self.app_callback = None
    
    def sys_misc(self, *args):
        pass
    
    def sys_size(self, addr, tags, data, client_address):
        self.xsize, self.ysize = data
    
    def sys_host(self, addr, tags, data, client_address):
        pass
    
    def sys_port(self, addr, tags, data, client_address):
        host, port = self.server_address
        if port == data[0]:
            self.focused = True
            self.waffle_send('/sys/prefix', GRIDDLE_PREFIX)
        else:
            self.focused = False
            print "lost focus (device changed port)"
    
    # prefix confirmation
    def sys_prefix(self, addr, tags, data, client_address):
        self.prefix = fix_prefix(data[0])

class Virtual(OSCServer, Waffle):
    def __init__(self, id, xsize, ysize, port=0):
        OSCServer.__init__(self, ('', port))
        self.id = id
        self.xsize = xsize
        self.ysize = ysize
        self.app_host = DEFAULT_APP_HOST
        self.app_port = DEFAULT_APP_PORT
        self.prefix = DEFAULT_APP_PREFIX
        
        self.addMsgHandler('default', self.waffle_handler)
        self.addMsgHandler('/sys/port', self.sys_port)
        self.addMsgHandler('/sys/host', self.sys_host)
        self.addMsgHandler('/sys/prefix', self.sys_prefix)

        self.addMsgHandler('/sys/connect', self.sys_misc)
        self.addMsgHandler('/sys/disconnect', self.sys_misc)
        self.addMsgHandler('/sys/rotation', self.sys_misc)
        
        self.addMsgHandler('/sys/info', self.sys_info)

        self.app_callback = None
    
    def sys_misc(self, addr, tags, data, client_address):
        pass

    def sys_port(self, addr, tags, data, client_address):
        self.waffle_send('/sys/port', self.app_port)
        self.app_port = data[0]
        self.waffle_send('/sys/port', self.app_port)
    
    def sys_host(self, addr, tags, data, client_address):
        self.waffle_send('/sys/host', self.app_host)
        self.app_host = data[0]
        self.waffle_send('/sys/host', self.app_host)
    
    def sys_prefix(self, addr, tags, data, client_address):
        self.prefix = fix_prefix(data[0])
        self.waffle_send('/sys/prefix', self.prefix)
    
    def sys_info(self, addr, tags, data, client_address):
        if len(data) == 2: host, port = data
        elif len(data) == 1: host, port = self.app_host, data[0]
        elif len(data) == 0: host, port = self.app_host, self.app_port
        else: return
        
        self.waffle_send_any(host, port, '/sys/id', self.id)
        self.waffle_send_any(host, port, '/sys/size', self.xsize, self.ysize)
        self.waffle_send_any(host, port, '/sys/host', self.app_host)
        self.waffle_send_any(host, port, '/sys/port', self.app_port)
        self.waffle_send_any(host, port, '/sys/prefix', self.prefix)
        self.waffle_send_any(host, port, '/sys/rotation', 0)
    
    # FIXME: we have to redefine these until the client behaviour is figured out 
    def waffle_send_any(self, host, port, path, *args):
        msg = OSCMessage(path)
        map(msg.append, args)
        client = OSCClient()
        client.sendto(msg, (host, port), timeout=0)
    
    def waffle_send(self, path, *args):
        msg = OSCMessage(path)
        map(msg.append, args)
        client = OSCClient()
        client.sendto(msg, (self.app_host, self.app_port), timeout=0)

class MonomeWatcher:
    def __init__(self, app):
        self.app = app
        self.sdRef = pybonjour.DNSServiceBrowse(regtype=REGTYPE, callBack=self.browse_callback)
        self.resolved = []
    
    def resolve_callback(self, sdRef, flags, interfaceIndex, errorCode, fullname, hosttarget, port, txtRecord):
        self.resolved.append(True)
        self.resolved_host = hosttarget
        self.resolved_port = port
    
    def browse_callback(self, sdRef, flags, interfaceIndex, errorCode, serviceName, regtype, replyDomain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return

        # ignore our own stuff
        if serviceName.startswith(GRIDDLE_SERVICE_PREFIX):
            return

        # FIXME: IPV4 and IPv6 are separate services and are resolved twice
        if not (flags & pybonjour.kDNSServiceFlagsAdd):
            self.app.monome_removed(serviceName)
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
        
        self.app.monome_discovered(serviceName, self.resolved_host, self.resolved_port)

class Griddle:
    def __init__(self, config='griddle.conf'):
        self.devices    = {}
        self.services   = {}
        self.offsets    = {}
        self.transtbl   = {}
        self.watcher = MonomeWatcher(self)
        
        self.parse_config(config)
    
    def parse_config(self, filename):
        from ConfigParser import RawConfigParser
        config = RawConfigParser()
        config.read(filename)
        for s in config.sections():
            port = int(config.get(s, 'port'))
            config.remove_option(s, 'port')
            
            xsize, ysize = [int(d) for d in config.get(s, 'size').split(",")]
            config.remove_option(s, 'size')
            
            x_off, y_off = [int(d) for d in config.get(s, 'offset').split(",")]
            config.remove_option(s, 'offset')
            self.offsets[s] = (x_off, y_off)
            
            for device, offset in config.items(s):
                x_off, y_off = [int(d) for d in offset.split(",")]
                if self.offsets.has_key(device):
                    if (x_off, y_off) != self.offsets[device]:
                        raise RuntimeError("conflicting offsets for device %s" % device)
                self.offsets[device] = (x_off, y_off)
                
                if s in self.transtbl: self.transtbl[s].append(device)
                else: self.transtbl[s] = [device]
                if device in self.transtbl: self.transtbl[device].append(s)
                else: self.transtbl[device] = [s]
            
            self.add_virtual(s, xsize, ysize, port)
    
    def add_virtual(self, name, xsize, ysize, port=0):
        device = Virtual(name, xsize, ysize, port)
        self.devices[name] = device
        
        sphost, spport = device.server_address
        service_name = '%s-%s' % (GRIDDLE_SERVICE_PREFIX, name)
        self.services[name] = pybonjour.DNSServiceRegister(name=service_name,
            regtype=REGTYPE,
            port=port,
            callBack=None)
        print "creating %s (%d)" % (name, spport)
        device.app_callback = self.route

    def monome_discovered(self, serviceName, host, port):
        name = serviceName.split()[-1].strip('()') # take serial
        if not name in self.offsets: # only take affected devices
            return
        
        # FIXME: IPV4 and IPv6 are separate services and are resolved twice
        if not self.devices.has_key(name):
            monome = Monome(name, (host, port))
            print "%s discovered" % name
            self.devices[name] = monome
            self.devices[name].app_callback = self.route
    
    def monome_removed(self, serviceName):
        name = serviceName.split()[-1].strip('()') # take serial
        # FIXME: IPV4 and IPv6 are separate services and are removed twice
        if self.devices.has_key(name):
            self.devices[name].close()
            del self.devices[name]
            print "%s removed" % name
        return
    
    def route(self, source, addr, tags, data):
        tsign = 1 if len(self.transtbl[source]) > 1 else -1
        
        # we have to sort devices by offset for correct splitting of row messages
        # FIXME: need to move all the offset calculation / clipping / tsign stuff to the config parser
        valid_targets = sorted(set(self.transtbl[source]) & set(self.devices.keys()), key=lambda k: self.offsets[k])
        valid_targets.reverse()
        
        #for d in self.transtbl[source]:
        for d in valid_targets:
            dest = self.devices[d]
            
            sxoff, syoff = self.offsets[source]
            dxoff, dyoff = self.offsets[d]
            xoff, yoff = tsign * (sxoff + dxoff),  tsign * (syoff + dyoff)
            
            # clipping adjustments
            if tsign == -1:
                minx = sxoff
                miny = syoff
                maxx = sxoff + self.devices[source].xsize
                maxy = syoff + self.devices[source].ysize
            else:
                minx = 0
                miny = 0
                maxx = dest.xsize
                maxy = dest.ysize
            
            if addr.endswith("grid/key") or addr.endswith("grid/led/set") or addr.endswith("grid/led/map"):
                x, y, args = data[0], data[1], data[2:]
                x, y = x - xoff, y - yoff
                if minx <= x < maxx and miny <= y < maxy:
                    dest.waffle_send('%s%s' % (dest.prefix, addr), x, y, *args)
            elif addr.endswith("grid/led/row"):
                x, y, args = data[0], data[1], data[2:]
                x, y = x - xoff, y - yoff
                args, remainder = args[:(maxx - minx) / 8], args[(maxx - minx) / 8:]
                if minx <= x < maxx and miny <= y < maxy:
                    dest.waffle_send('%s%s' % (dest.prefix, addr), x, y, *args)
                if len(remainder) > 0:
                    # tags=None (ignored)
                    self.route(source, addr, None, [x+dest.xsize, y]+remainder)
            elif addr.endswith("grid/led/col"):
                x, y, args = data[0], data[1], data[2:]
                x, y = x - xoff, y - yoff
                args, remainder = args[:(maxy - miny) / 8], args[(maxy - miny) / 8:]
                if minx <= x < maxx and miny <= y < maxy:
                    dest.waffle_send('%s%s' % (dest.prefix, addr), x, y, *args)
                if len(remainder) > 0:
                    # tags=None (ignored)
                    self.route(source, addr, None, [x, y+dest.ysize]+remainder)
            # special-case for /led/map in splitter configuration
            elif addr.endswith("grid/led/all") and tsign == -1:
                for x in range(minx, maxx, 8):
                    for y in range(miny, maxy, 8):
                        # tags=None (ignored)
                        self.route(source, "/grid/led/map", None, [x,y]+[0,0,0,0,0,0,0,0])
            else:
                dest.waffle_send('%s%s' % (dest.prefix, addr), data)
    
    def run(self):
        while True:
            rlist = itertools.chain(self.devices.values(),
                self.services.values(),
                [self.watcher.sdRef])
            ready = select.select(rlist, [], [])
            for r in ready[0]:
                if isinstance(r, OSCServer):
                    r.handle_request()
                elif isinstance(r, pybonjour.DNSServiceRef):
                    pybonjour.DNSServiceProcessResult(r)
                else:
                    raise RuntimeError("unknown stuff in select: %s", r)
    
    def close(self):
        rlist = itertools.chain(self.devices.values(),
            self.services.values(),
            [self.watcher.sdRef])
        for s in rlist:
            s.close()

try:
    conf_file = sys.argv[1]
except IndexError:
    print "need configuration file to run!"
    sys.exit(1)

app = Griddle(conf_file)
try:
    app.run()
except KeyboardInterrupt:
    pass
finally:
    app.close()
