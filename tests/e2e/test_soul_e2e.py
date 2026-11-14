"""Unified Soul Link flow with real local app processes and private-by-default views."""
import json
import unittest
import uuid

from tests.e2e.test_demo_e2e import (ARTIFACTS, CSP_PROBE, DemoServer, ENABLED,
                                    SERVER_START_TIMEOUT, SKIP_REASON,
                                    expect, sync_playwright)


@unittest.skipUnless(ENABLED, SKIP_REASON)
class SoulExperienceBrowserTests(unittest.TestCase):
    def test_common_invite_private_views_manual_events_resume_and_dynamic_membership(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        servers, pages, profiles = [], [], []
        errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={'width': 1366, 'height': 1000}, locale='es-ES')
            context.add_init_script(CSP_PROBE)
            def open_app(index, profile=None):
                profile = profile or 'e2e-soul-'+uuid.uuid4().hex[:12]
                server = DemoServer(ARTIFACTS / f'soul-server-{index}.log', profile)
                servers.append(server)
                page = context.new_page()
                page.set_default_timeout(30000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('dialog', lambda dialog: dialog.accept())
                page.goto(server.wait_ready(SERVER_START_TIMEOUT), wait_until='domcontentloaded')
                expect(page.locator('#party > article.card')).to_have_count(6)
                page.locator('details.options > summary').click()
                page.locator('#open-companion').click()
                expect(page.locator('#companion-transport')).to_have_value('soul')
                page.locator('#companion-name').fill('Amigo '+str(index+1))
                return server, page, profile
            def refresh(page):
                page.locator('#companion-refresh').click()
                expect(page.locator('#companion-refresh')).to_be_enabled()
                return page.evaluate("async()=>await(await fetch('/api/companion')).json()")
            def post(page, command):
                return page.evaluate("""async command=>{const r=await fetch('/api/command',{
                    method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},
                    body:JSON.stringify(command)});return r.status;}""", command)
            def stop(server):
                server.stop()
                if server.process.stdout:
                    server.process.stdout.close()
            try:
                for index in range(5):
                    server, page, profile = open_app(index)
                    pages.append(page)
                    profiles.append(profile)
                host = pages[0]
                host.locator('#companion-advanced > summary').click()
                host.locator('#companion-host').fill('127.0.0.1')
                host.locator('#companion-port').fill('0')
                expect(host.locator('#room-capacity-label')).to_be_hidden()
                host.locator('#companion-advanced > summary').click()
                host.locator('#companion-direct-host').click()
                expect(host.locator('#room-summary')).to_contain_text('1/4')
                expect(host.locator('#companion-refresh')).to_be_enabled()
                self.assertLessEqual(host.locator('#companion-dialog').bounding_box()['width'], 700)
                expect(host.locator('#soul-sharing')).not_to_be_checked()
                invitation = host.locator('#companion-share').input_value()
                self.assertIn('/soul#', invitation)
                host.screenshot(path=str(ARTIFACTS / 'soul-room-1.png'), mask=[host.locator('#companion-share')], mask_color='#d5d9df')
                for i in range(1, 4):
                    pages[i].locator('#companion-invite').fill(invitation)
                    pages[i].locator('#companion-join').click()
                    expect(pages[i].locator('#room-roster > article')).to_have_count(i+1)
                    refresh(host)
                    expect(host.locator('#room-summary')).to_contain_text(str(i+1)+'/4')
                    if i == 1:
                        self.assertLessEqual(host.locator('#companion-dialog').bounding_box()['width'], 880)
                    self.assertEqual(host.locator('#companion-share').input_value(), invitation)
                    host.screenshot(path=str(ARTIFACTS / f'soul-room-{i+1}.png'), mask=[host.locator('#companion-share')], mask_color='#d5d9df')
                for page in pages[:4]:
                    status = refresh(page)
                    self.assertEqual(status['protocol'], 3)
                    self.assertTrue(all(not m['sharing'] and m['state'] is None for m in status['room']['members']))
                    expect(page.locator('#room-roster > article')).to_have_count(4)
                    expect(page.locator('#room-roster .room-team')).to_have_count(0)
                    self.assertEqual(page.locator('#soul-sharing').count(), 1)
                pages[4].locator('#companion-invite').fill(invitation)
                pages[4].locator('#companion-join').click()
                expect(pages[4].locator('#companion-status')).to_contain_text('llena')
                # Every player controls only their own full-view permission.
                for index, page in enumerate(pages[:4]):
                    page.locator('#soul-sharing').check()
                    expect(page.locator('#companion-refresh')).to_be_enabled()
                    observer = pages[1] if index == 0 else host
                    status = refresh(observer)
                    target = next(m for m in status['room']['members'] if m['name'] == 'Amigo '+str(index+1))
                    self.assertTrue(target['sharing'])
                    self.assertIsNotNone(target['state'])
                    page.locator('#soul-sharing').uncheck()
                    expect(page.locator('#companion-refresh')).to_be_enabled()
                    status = refresh(observer)
                    target = next(m for m in status['room']['members'] if m['name'] == 'Amigo '+str(index+1))
                    self.assertFalse(target['sharing'])
                    self.assertIsNone(target['state'])
                # Withdrawal removes a currently viewed full team and detail caches.
                self.assertEqual(post(pages[2], {'action': 'demo', 'scenario': 'long'}), 202)
                pages[2].wait_for_function("()=>localState.party[0].nickname==='Nombre de prueba muy largo'")
                pages[2].locator('#soul-sharing').check()
                expect(pages[2].locator('#companion-refresh')).to_be_enabled()
                refresh(host)
                host.locator('#room-roster > article').nth(2).get_by_role('button', name='Ver partida', exact=True).click()
                host.locator('#party > article.card').first.click()
                expect(host.locator('#detail')).to_be_visible()
                pages[2].locator('#soul-sharing').uncheck()
                expect(host.locator('#detail')).not_to_be_visible(timeout=25000)
                self.assertIsNone(host.evaluate('detailPokemon'))
                self.assertNotIn('Nombre de prueba muy largo', host.locator('body').text_content())
                expect(host.locator('nav button[data-tab="connection"]')).to_be_enabled()
                host.locator('details.options > summary').click()
                host.locator('#open-companion').click()
                # Linked capture selectors continue to work while everybody is private.
                for page in pages[:4]:
                    refresh(page)
                    selector = page.get_by_label('Tu captura en Ruta 1', exact=True)
                    expect(selector).to_be_enabled()
                    selector.select_option('33:1000')
                    expect(selector).to_be_enabled()
                    expect(selector).to_have_value('33:1000')
                status = refresh(host)
                self.assertTrue(all(m['links'].get('alola:8') == '33:1000' and m['state'] is None for m in status['room']['members']))
                host.locator('#soullink-enabled').check()
                refresh(host)
                host.locator('#companion-close').click()
                self.assertEqual(post(pages[1], {'action': 'mark_dead', 'key': '33:1000'}), 202)
                expect(host.locator('#soullink-notification')).to_be_visible(timeout=25000)
                before = host.evaluate("async()=>await(await fetch('/api/state')).json()")
                self.assertNotIn('33:1000', before['progress']['deaths'])
                host.locator('#soullink-kill').click()
                host.wait_for_function("()=>Boolean(localState.progress.deaths['33:1000'])")
                after = host.evaluate("async()=>await(await fetch('/api/state')).json()")
                self.assertEqual(after['progress']['deaths']['33:1000']['source'], 'soullink-response')
                for page in pages[2:4]:
                    state = page.evaluate("async()=>await(await fetch('/api/state')).json()")
                    self.assertNotIn('33:1000', state['progress']['deaths'])
                host.locator('details.options > summary').click()
                host.locator('#open-companion').click()
                # Responsive and keyboard inspection uses synthetic data, invitation masked.
                for width, height, name in ((1366, 1000, 'desktop'), (840, 900, 'medium'), (390, 844, 'mobile')):
                    host.set_viewport_size({'width': width, 'height': height})
                    host.screenshot(path=str(ARTIFACTS / f'soul-private-{name}.png'), mask=[host.locator('#companion-share')], mask_color='#d5d9df')
                    self.assertTrue(host.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                host.set_viewport_size({'width': 1366, 'height': 1000})
                host.locator('#soul-sharing').focus()
                host.keyboard.press('Tab')
                self.assertNotEqual(host.evaluate('document.activeElement.tagName'), 'BODY')
                # Revoke admission, keep individual membership and secure restart proof.
                host.locator('#soul-admin > summary').click()
                host.locator('#soul-revoke').click()
                expect(host.locator('#companion-share')).to_be_hidden()
                old_id = refresh(host)['room']['members'][3]['player_id']
                stop(servers[3])
                expect(host.locator('#room-roster > article').nth(3)).to_contain_text('plaza reservada', timeout=30000)
                replacement_server, restarted, _ = open_app(3, profiles[3])
                pages[3] = restarted
                restarted.locator('#companion-invite').fill(invitation)
                restarted.locator('#companion-join').click()
                expect(restarted.locator('#room-roster > article')).to_have_count(4)
                status = refresh(host)
                self.assertEqual(status['room']['members'][3]['player_id'], old_id)
                self.assertFalse(status['room']['members'][3]['sharing'])
                # Voluntary leave frees a place; a new player never inherits it.
                restarted.locator('#companion-leave').click()
                expect(restarted.locator('#companion-setup')).to_be_visible()
                refresh(host)
                expect(host.locator('#room-summary')).to_contain_text('3/4')
                if not host.locator('#soul-admin').evaluate('node=>node.open'):
                    host.locator('#soul-admin > summary').click()
                host.locator('#soul-regenerate').click()
                expect(host.locator('#companion-share')).to_be_visible()
                new_invitation = host.locator('#companion-share').input_value()
                self.assertNotEqual(new_invitation, invitation)
                pages[4].locator('#companion-invite').fill(new_invitation)
                pages[4].locator('#companion-join').click()
                expect(pages[4].locator('#room-roster > article')).to_have_count(4)
                status = refresh(host)
                new_id = next(m['player_id'] for m in status['room']['members'] if m['name'] == 'Amigo 5')
                self.assertNotEqual(new_id, old_id)
                self.assertNotIn(old_id, [m['player_id'] for m in status['room']['members']])
                self.assertEqual(errors, [])
                for page in pages:
                    if not page.is_closed():
                        self.assertEqual(page.evaluate('window.__cspViolations'), [])
                (ARTIFACTS / 'soul-result.json').write_text(json.dumps({'same_link_admissions': 3,
                    'fifth_rejected': True, 'private_default': True, 'sharing_per_player': True,
                    'manual_private_events': True, 'resume_after_revoke': True, 'released_slot_reused_safely': True,
                    'transport': 'loopback', 'gameplay_verified': False, 'native_webview2_verified': False}), encoding='utf-8')
            finally:
                context.close()
                browser.close()
                for server in servers:
                    stop(server)


if __name__ == '__main__':
    unittest.main()
