"""Isolated real HTTP: admission does not authorize member actions or local administration."""
import http.client
import json
import unittest
import uuid
from contextlib import closing

from companion.soul_direct import MAX_REQUEST_BYTES, SoulHost, soul_invitation, soul_request
from companion.soul_room import FEATURES


def identity(name):
    return {'player_id': str(uuid.uuid4()), 'run_id': str(uuid.uuid4()),
            'name': name, 'game': 'Ultra Sun 1.0'}


class SoulTransportTests(unittest.TestCase):
    def setUp(self):
        self.host = SoulHost('127.0.0.1', 0, identity('Host'))
        self.addCleanup(self.host.close)
        self.base, self.secret = soul_invitation(self.host.link())

    def join(self, name='Peer'):
        person = identity(name)
        response = soul_request(self.base, '/v3/join', self.secret,
                                {'protocol': 3, 'features': FEATURES, **person})
        return person, response['token']

    def envelope(self, person, seq=1):
        return {'protocol': 3, 'session_id': self.host.room.session_id, 'epoch': self.host.room.epoch,
                'run_id': person['run_id'], 'sequence': seq, 'sharing': False, 'source_live': True,
                'state': None, 'links': {}, 'soul': {'captures': {}, 'missed_routes': []}}

    def test_common_admission_cannot_authorize_exchange_resume_or_administration(self):
        person, token = self.join()
        for path in ('/v3/exchange', '/v3/resume', '/v3/leave'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '401'):
                soul_request(self.base, path, self.secret, self.envelope(person))
        for path in ('/api/command', '/api/companion', '/v1/exchange', '/v2/exchange'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '404'):
                soul_request(self.base, path, token, self.envelope(person))
        result = soul_request(self.base, '/v3/exchange', token, self.envelope(person))
        self.assertEqual(len(result['room']['members']), 2)
        self.assertEqual(self.host.room.authenticate(token), person['player_id'])

    def test_origin_host_content_type_duplicate_length_and_size_are_rejected(self):
        for headers, expected in (
            ({'Origin': 'https://not-the-local-app.invalid'}, 403),
            ({'Host': 'not-the-room.invalid'}, 403),
            ({'Content-Type': 'text/plain'}, 415),
            ({'Content-Length': str(MAX_REQUEST_BYTES + 1)}, 413)):
            with self.subTest(headers=headers):
                with closing(http.client.HTTPConnection('127.0.0.1', self.host.server.server_port, timeout=3)) as connection:
                    connection.request('POST', '/v3/join', b'{}', {'Content-Type': 'application/json',
                        'Authorization': 'Bearer '+self.secret, **headers})
                    reply = connection.getresponse()
                    self.assertEqual(reply.status, expected)
                    reply.read()
        with closing(http.client.HTTPConnection('127.0.0.1', self.host.server.server_port, timeout=3)) as connection:
            connection.putrequest('POST', '/v3/join')
            connection.putheader('Authorization', 'Bearer '+self.secret)
            connection.putheader('Content-Type', 'application/json')
            connection.putheader('Content-Length', '2')
            connection.putheader('Content-Length', '2')
            connection.endheaders(b'{}')
            reply = connection.getresponse()
            self.assertEqual(reply.status, 400)
            reply.read()
        self.assertEqual(len(self.host.room.members), 1)

    def test_authenticated_burst_limit_is_bounded_and_private_response_has_no_secrets(self):
        person, token = self.join()
        results = []
        rejected = False
        for seq in range(1, 11):
            try:
                results.append(soul_request(self.base, '/v3/exchange', token, self.envelope(person, seq)))
            except ValueError as error:
                self.assertIn('429', str(error))
                rejected = True
        self.assertTrue(rejected)
        self.assertLessEqual(len(self.host.rates), 5)
        self.assertLessEqual(self.host.room.members[person['player_id']]['sequence'], 8)
        raw = json.dumps(results)
        self.assertNotIn(token, raw)
        self.assertNotIn(self.secret, raw)
        self.assertTrue(all(m['state'] is None for result in results for m in result['room']['members']))


if __name__ == '__main__':
    unittest.main()
