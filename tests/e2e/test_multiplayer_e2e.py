"""Four real app processes + Chromium. Demonstration data, never an emulator."""
import json
import unittest
import uuid

from tests.e2e.test_demo_e2e import (ARTIFACTS, CSP_PROBE, DemoServer, ENABLED,
                                    SERVER_START_TIMEOUT, SKIP_REASON,
                                    expect, sync_playwright)


@unittest.skipUnless(ENABLED, SKIP_REASON)
class MultiplayerBrowserTests(unittest.TestCase):
    def test_four_apps_links_manual_death_readonly_responsive_and_leave(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        servers, pages = [], []
        errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={'width': 1366, 'height': 1000}, locale='es-ES')
            context.add_init_script(CSP_PROBE)
            try:
                for i in range(4):
                    server = DemoServer(ARTIFACTS / f'room-server-{i}.log', 'e2e-room-'+uuid.uuid4().hex[:12])
                    servers.append(server)
                    page = context.new_page()
                    pages.append(page)
                    page.set_default_timeout(25000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(server.wait_ready(SERVER_START_TIMEOUT), wait_until='domcontentloaded')
                    expect(page.locator('#party > article.card')).to_have_count(6)
                    page.locator('details.options > summary').click()
                    page.locator('#open-companion').click()
                    page.locator('#companion-advanced > summary').click()
                    page.locator('#companion-transport').select_option('room')
                    page.locator('#companion-name').fill('Jugador '+str(i+1))
                host = pages[0]
                host.locator('#companion-host').fill('127.0.0.1')
                host.locator('#companion-port').fill('0')
                host.locator('#room-capacity').select_option('4')
                host.locator('#companion-direct-host').click()
                expect(host.locator('#room-roster > article')).to_have_count(1)
                for i in range(1, 4):
                    if i > 1:
                        host.locator('#room-invite').click()
                    expect(host.locator('#companion-share')).not_to_have_value('')
                    invitation = host.locator('#companion-share').input_value()
                    pages[i].locator('#companion-invite').fill(invitation)
                    pages[i].locator('#companion-join').click()
                    expect(pages[i].locator('#room-roster > article')).to_have_count(i+1)
                    host.locator('#companion-refresh').click()
                    expect(host.locator('#room-roster > article')).to_have_count(i+1)
                for page in pages:
                    page.locator('#companion-refresh').click()
                    expect(page.locator('#companion-refresh')).to_be_enabled()
                    expect(page.locator('#room-roster > article')).to_have_count(4)
                    choice = page.get_by_label('Tu captura en Ruta 1', exact=True)
                    expect(choice).to_be_enabled()
                    choice.select_option('33:1000')
                    expect(choice).to_be_enabled()
                    expect(choice).to_have_value('33:1000')
                    saved = page.evaluate("async()=>await(await fetch('/api/companion')).json()")
                    own_member = next(m for m in saved['room']['members'] if m['player_id'] == saved['player_id'])
                    self.assertEqual(own_member['links'].get('alola:8'), '33:1000')
                host.locator('#companion-refresh').click()
                expect(host.locator('#companion-refresh')).to_be_enabled()
                shared = host.evaluate("async()=>await(await fetch('/api/companion')).json()")
                self.assertTrue(all(m['links'].get('alola:8') == '33:1000' for m in shared['room']['members']))
                # Responsive layout and actual remote read-only rendering.
                host.screenshot(path=str(ARTIFACTS / 'room-four-desktop.png'), full_page=True)
                host.set_viewport_size({'width': 390, 'height': 844})
                host.screenshot(path=str(ARTIFACTS / 'room-four-mobile.png'), full_page=True)
                self.assertTrue(host.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
                host.set_viewport_size({'width': 1366, 'height': 1000})
                host.locator('#room-roster > article').nth(1).get_by_role('button', name='Ver partida · solo lectura').click()
                expect(host.locator('nav button[data-tab="connection"]')).to_be_disabled()
                expect(host.locator('nav button[data-tab="progress"]')).to_be_disabled()
                host.locator('#companion-toggle').click()
                expect(host.locator('nav button[data-tab="connection"]')).to_be_enabled()
                host.locator('details.options > summary').click()
                host.locator('#open-companion').click()
                host.locator('#soullink-enabled').check()
                # Establish notification baseline after opt-in before creating a death.
                host.locator('#companion-refresh').click()
                expect(host.locator('#companion-refresh')).to_be_enabled()
                host.locator('#companion-close').click()
                response = pages[1].evaluate("""async()=>{const r=await fetch('/api/command',{
                  method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},
                  body:JSON.stringify({action:'mark_dead',key:'33:1000'})});return r.status;}""")
                self.assertEqual(response, 202)  # The real API queues validated local commands.
                expect(host.locator('#soullink-notification')).to_be_visible(timeout=25000)
                before = host.evaluate("async()=>await(await fetch('/api/state')).json()")
                self.assertNotIn('33:1000', before['progress']['deaths'])
                host.locator('#soullink-kill').click()
                host.wait_for_function("()=>Boolean(localState.progress.deaths['33:1000'])")
                after = host.evaluate("async()=>await(await fetch('/api/state')).json()")
                self.assertEqual(after['progress']['deaths']['33:1000']['source'], 'soullink-response')
                for page in pages[2:]:
                    current = page.evaluate("async()=>await(await fetch('/api/state')).json()")
                    self.assertNotIn('33:1000', current['progress']['deaths'])
                # Guest leave is explicit and does not silently free/reassign a slot.
                pages[3].on('dialog', lambda dialog: dialog.accept())
                pages[3].locator('#companion-leave').click()
                host.locator('details.options > summary').click()
                host.locator('#open-companion').click()
                host.locator('#companion-refresh').click()
                expect(host.locator('#room-roster > article').nth(3)).to_contain_text('Salió de la sala')
                self.assertEqual(errors, [])
                for page in pages:
                    self.assertEqual(page.evaluate('window.__cspViolations'), [])
                (ARTIFACTS / 'room-result.json').write_text(json.dumps({'processes': 4, 'players': 4,
                    'transport': 'loopback', 'manual_confirmation': True,
                    'read_only': True, 'gameplay_verified': False}), encoding='utf-8')
            finally:
                for page in pages:
                    try:
                        page.screenshot(path=str(ARTIFACTS / f'room-final-{pages.index(page)}.png'), full_page=True)
                    except Exception:
                        pass
                context.close()
                browser.close()
                for server in servers:
                    server.stop()
                    if server.process.stdout:
                        server.process.stdout.close()


if __name__ == '__main__':
    unittest.main()
