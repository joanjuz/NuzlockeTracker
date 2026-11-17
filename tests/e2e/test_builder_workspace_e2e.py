"""Persistent builder panels and full virtual analysis in a real browser."""
import unittest
import uuid

from tests.e2e import test_demo_e2e as demo


@unittest.skipUnless(demo.ENABLED, demo.SKIP_REASON)
class BuilderWorkspaceTests(unittest.TestCase):
    setUpClass = classmethod(demo.DemoBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(demo.DemoBrowserTests.tearDownClass.__func__)
    setUp = demo.DemoBrowserTests.setUp
    tearDown = demo.DemoBrowserTests.tearDown
    _known = staticmethod(demo.DemoBrowserTests._known)
    _on_console = demo.DemoBrowserTests._on_console
    _on_response = demo.DemoBrowserTests._on_response
    assert_clean = demo.DemoBrowserTests.assert_clean
    open_tracker = demo.DemoBrowserTests.open_tracker
    open_tab = demo.DemoBrowserTests.open_tab

    def test_available_panel_and_virtual_analysis_survive_builder_actions(self):
        self.open_tracker()
        self.open_tab('analysis')
        page = self.page
        page.locator('#analysis-section-builder').click()
        catalog = page.locator('.builder-catalog')
        catalog.locator('summary').click()
        page.locator('#builder-use-party').click()
        demo.expect(catalog).to_have_attribute('open', '')
        page.locator('[data-builder-remove="0"]').click()
        page.locator('#builder-candidates [data-builder-toggle][aria-pressed="false"]').first.click()
        page.locator('[data-builder-move="0:1"]').click()
        page.locator('#builder-sort').select_option('bst')
        page.locator('#builder-source').select_option('party')
        page.locator('#builder-search').fill('a')
        page.locator('#builder-search').focus()
        page.evaluate("state.party[0].level++;builderSignature='';renderTeamBuilder()")
        demo.expect(page.locator('#builder-search')).to_be_focused()
        demo.expect(page.locator('#builder-search')).to_have_value('a')
        demo.expect(page.locator('#builder-sort')).to_have_value('bst')
        demo.expect(catalog).to_have_attribute('open', '')
        page.locator('#builder-abilities').uncheck()
        page.locator('#builder-team [data-analysis-mega]').first.click()
        demo.expect(catalog).to_have_attribute('open', '')
        demo.expect(page.locator('#builder-report .fx-row')).to_have_count(18)
        row = page.locator('#builder-report .fx-row').first
        row.locator('summary').click()
        type_name = row.locator('.fx-type').inner_text()
        page.locator('[data-builder-remove="0"]').click()
        demo.expect(page.locator('#builder-report .fx-row').filter(has=page.get_by_text(type_name, exact=True)).first).to_have_attribute('open', '')
        page.locator('#builder-abilities').check()
        demo.expect(page.locator('#builder-report .fx-row').filter(has=page.get_by_text(type_name, exact=True)).first).to_have_attribute('open', '')
        page.locator('#builder-defense-display').select_option('table')
        page.locator('#builder-defense-sort').select_option('type')
        demo.expect(page.locator('#builder-report .analysis-table tbody tr')).to_have_count(18)
        demo.expect(page.locator('#builder-defense-display')).to_have_value('table')
        page.locator('#builder-defense-display').select_option('chart')
        demo.expect(page.locator('#builder-report .fx-row').filter(has=page.get_by_text(type_name, exact=True)).first).to_have_attribute('open', '')
        page.locator('#builder-defense-display').select_option('table')
        page.locator('.builder-library > summary').click()
        page.locator('#builder-name').fill('Panel ' + uuid.uuid4().hex)
        with page.expect_response(lambda response: '/api/teams' in response.url and response.request.method == 'POST') as saved:
            page.locator('#builder-save').click()
        self.assertEqual(saved.value.status, 200, saved.value.text())
        demo.expect(page.locator('#builder-saved-status')).not_to_be_empty()
        demo.expect(catalog).to_have_attribute('open', '')
        demo.expect(page.locator('#builder-defense-display')).to_have_value('table')
        page.locator('#builder-name').fill('Renombrado ' + uuid.uuid4().hex)
        page.locator('#builder-rename').click()
        demo.expect(page.locator('#builder-saved-status')).to_have_text('Nombre cambiado.')
        demo.expect(catalog).to_have_attribute('open', '')
        page.on('dialog', lambda dialog: dialog.accept())
        page.locator('#builder-delete').click()
        demo.expect(page.locator('#builder-saved')).to_have_value('')
        demo.expect(page.locator('#builder-report .coverage-cell')).to_have_count(18)
        page.keyboard.press('Escape')
        demo.expect(catalog).to_have_attribute('open', '')
        page.set_viewport_size({'width': 600, 'height': 800})
        page.locator('.options > summary').click()
        page.locator('#theme').select_option('dark')
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 600)
        catalog.locator('summary').click()
        demo.expect(catalog).not_to_have_attribute('open', '')
        self.assert_clean()


if __name__ == '__main__':
    unittest.main()
