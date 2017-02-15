# Copyright (C) 2016 Roberto Riggio.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from uuid import UUID
from uuid import uuid4
from webob import Response

from ryu.app.wsgi import ControllerBase, route
from ryu.ofproto.ofproto_v1_0_parser import OFPMatch
from ryu.ofproto.ofproto_v1_0_parser import OFPFlowMod
from ryu.lib import dpid as dpid_lib


def empower_to_dpid(mac):
    """Convert from empower format to dpid."""

    if not mac:
        return None

    return dpid_lib.str_to_dpid('{:<16}'.format(mac.replace(':', '')))


def dpid_to_empower(dpid):
    """Convert from dpid format to empower."""

    if not dpid:
        return None

    tmp = dpid_lib.dpid_to_str(dpid)
    tmp = tmp[2:]

    return ':'.join(tmp[i:i + 2] for i in range(0, len(tmp), 2))


class IntentRule(object):

    def __init__(self, uuid, rule):

        self.uuid = uuid
        self.ttp_dpid = empower_to_dpid(rule['ttp_dpid'])
        self.ttp_port = int(rule['ttp_port'])
        self.match = rule['match']
        self.stp_dpid = None
        self.stp_port = None
        self.flow_mods = []
        self.stp_dpid = empower_to_dpid(rule['stp_dpid'])
        self.stp_port = int(rule['stp_port'])

    def to_jsondict(self):
        """Return JSON representation of this object."""

        out = {'ttp_dpid': dpid_to_empower(self.ttp_dpid),
               'ttp_port': self.ttp_port,
               'uuid': self.uuid,
               'stp_dpid': dpid_to_empower(self.stp_dpid),
               'stp_port': self.stp_port,
               'match': self.match,
               'flow_mods': self.flow_mods}

        return {'IntentRule': out}

    def __eq__(self, other):

        return self.ttp_dpid == other.ttp_dpid and \
               self.ttp_port == other.ttp_port and \
               self.match == other.match


class IntentPOA(object):

    def __init__(self, uuid, poa):

        self.uuid = uuid
        self.hwaddr = empower_to_dpid(poa['hwaddr'])
        self.dpid = empower_to_dpid(poa['dpid'])
        self.port = int(poa['port'])

    def to_jsondict(self):
        """Return JSON representation of this object."""

        out = {'dpid': dpid_to_empower(self.dpid),
               'port': self.port,
               'uuid': self.uuid,
               'hwaddr': dpid_to_empower(self.hwaddr)}

        return {'IntentPOA': out}

    def __eq__(self, other):

        return self.hwaddr == other.hwaddr and \
               self.dpid == other.dpid and \
               self.port == other.port


class IterEncoder(json.JSONEncoder):
    """Encode iterable objects as lists."""

    def default(self, obj):
        try:
            return list(obj)
        except TypeError:
            return super(IterEncoder, self).default(obj)


class IntentEncoder(IterEncoder):
    """Handle the representation of the EmPOWER datatypes in JSON format."""

    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, OFPMatch):
            ret = obj.to_jsondict()
            return ret['OFPMatch']
        if isinstance(obj, OFPFlowMod):
            ret = obj.to_jsondict()
            return ret['OFPFlowMod']
        if isinstance(obj, IntentRule):
            ret = obj.to_jsondict()
            return ret['IntentRule']
        if isinstance(obj, IntentPOA):
            ret = obj.to_jsondict()
            return ret['IntentPOA']
        return super(IntentEncoder, self).default(obj)


class IntentController(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(IntentController, self).__init__(req, link, data, **config)
        self.intent_app = data['intent_app']

    @route('intent', '/intent/poa', methods=['GET'])
    def get_poa(self, req, **kwargs):

        try:
            body = \
                json.dumps(self.intent_app.rules.values(), cls=IntentEncoder)
            return Response(content_type='application/json', body=body)
        except KeyError:
            return Response(status=404)
        except ValueError:
            return Response(status=400)

    @route('intent', '/intent/poa/{uuid}', methods=['GET'])
    def get_poa(self, req, **kwargs):

        try:
            uuid = UUID(kwargs['uuid'])
            body = json.dumps(self.intent_app.rules[uuid], cls=IntentEncoder)
            return Response(content_type='application/json', body=body)
        except KeyError:
            return Response(status=404)
        except ValueError:
            return Response(status=400)

    @route('intent', '/intent/poa', methods=['DELETE'])
    def delete_poa(self, req, **kwargs):

        try:
            self.intent_app.remove_rule(None)
            return Response(status=204)
        except KeyError:
            return Response(status=404)
        except ValueError:
            return Response(status=400)

    @route('intent', '/intent/poa/{uuid}', methods=['DELETE'])
    def delete_poa(self, req, **kwargs):

        try:
            uuid = UUID(kwargs['uuid'])
            self.intent_app.remove_rule(uuid)
            return Response(status=204)
        except KeyError:
            return Response(status=404)
        except ValueError:
            return Response(status=400)

    @route('intent', '/intent/poa/{uuid}', methods=['PUT'])
    def update_poa(self, req, **kwargs):

        try:

            body = json.loads(req.body)
            uuid = UUID(kwargs['uuid'])

            if uuid not in self.intent_app.rules:
                poa = IntentPOA(uuid, body)
                self.intent_app.add_rule(poa)
                return Response(status=201)

            poa = IntentPOA(uuid, body)
            self.intent_app.update_rule(uuid, poa)
            return Response(status=204)

        except KeyError:
            return Response(status=404)
        except ValueError:
            return Response(status=400)

    @route('intent', '/intent/poa', methods=['POST'])
    def add_poa(self, req, **kwargs):

        try:

            body = json.loads(req.body)
            poa = IntentPOA(uuid4(), body)

            self.intent_app.add_rule(poa)
            headers = {'Location': '/intent/poa/%s' % poa.uuid}

            return Response(status=201, headers=headers)

        except KeyError:
            return Response(status=404)
        except ValueError:
            return Response(status=400)

    @route('intent', '/ls/rules', methods=['GET'])
    def get_ls_poa(self, req, **kwargs):

        try:
            sorted_rules = self.intent_app.rules_str
            sorted_rules.sort()
            return Response(body=json.dumps('<br>'.join(sorted_rules)))

        except KeyError:
            return Response(status=404)

        except ValueError:
            return Response(status=400)
