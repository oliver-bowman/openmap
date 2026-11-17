"""Map FPS-cap migration in Lua 5.1: python -P tools/offline-test/fps.py."""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[2]


class MapFpsTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute((ROOT / "tools/offline-test/stub.lua").read_text(encoding="utf-8"))
        self.lua.execute("""
            ns = { Client = 'Forever', MapStitch = {
                viewHooks = {}, IsBuilt = function() return false end,
            } }
            cvars = { maxFPS = '120', mapFade = '1' }
            fpsWrites = {}
            function GetCVar(name) return cvars[name] or '0' end
            function SetCVar(name, value)
                cvars[name] = tostring(value)
                if name == 'maxFPS' then fpsWrites[#fpsWrites + 1] = tostring(value) end
            end
            C_CVar = { SetCVar = SetCVar }
        """)
        self.lua.execute((ROOT / "OpenMap/Core.lua").read_text(encoding="utf-8"),
                         "OpenMap", self.lua.globals().ns)
        self.lua.execute("""
            mod = ns:NewModule('worldmap')
            function mod.TimeAfter(_, fn, ...) return fn(...) end
            mod.TimeClose = mod.TimeAfter
        """)
        self.lua.execute((ROOT / "OpenMap/Map/Extras.lua").read_text(encoding="utf-8"),
                         "OpenMap", self.lua.globals().ns)
        self.lua.execute("""
            function Setup(saved, fps, shown, kept)
                OpenMapDB = { worldmap = saved }
                OpenMapCharDB = { worldmap = { cvars = kept or {} } }
                ns:InitDB()
                cvars.maxFPS = tostring(fps)
                map = CreateFrame('Frame', nil, UIParent)
                map.ScrollContainer = CreateFrame('Frame', nil, map)
                map.dataProviders, map.overlayFrames = {}, {}
                map:SetShown(shown)
                mod:SetupExtras(map)
            end
        """)

    def tearDown(self):
        self.assertEqual(list(self.lua.globals().ERRORS.values()), [])

    def test_old_default_is_migrated_before_applying_to_an_open_map(self):
        self.lua.execute("""
            Setup({ mapFpsCap = 60, fpsCap60 = true }, 120, true)
            assert(mod.db.mapFpsCap == 0 and mod.db.fpsCapGame)
            assert(cvars.maxFPS == '120', 'upgrade left the open map capped at 60')
            assert(#fpsWrites == 0, 'upgrade briefly applied the obsolete cap')
        """)

    def test_upgrade_releases_a_previously_held_cap(self):
        self.lua.execute("""
            Setup({ mapFpsCap = 60, fpsCap60 = true }, 60, true, { maxFPS = '144' })
            assert(cvars.maxFPS == '144', 'old held cap was not released immediately')
            assert(mod.char.cvars.maxFPS == nil)
        """)

    def test_cap_explicitly_chosen_after_migration_is_preserved(self):
        self.lua.execute("""
            Setup({ mapFpsCap = 60, fpsCapGame = true }, 120, false)
            for _ = 1, 3 do
                map:Show()
                mod.RefreshExtras()
                assert(cvars.maxFPS == '60' and mod.db.mapFpsCap == 60)
                map:Hide()
                assert(cvars.maxFPS == '120' and mod.char.cvars.maxFPS == nil)
            end
        """)


if __name__ == "__main__":
    unittest.main()
