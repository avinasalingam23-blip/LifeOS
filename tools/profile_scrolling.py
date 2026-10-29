"""Profile actual overflowing record-list draws, in both themes, offline."""
from pathlib import Path
import cProfile
import io
import json
import pstats
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from lifeos.db import Database
    from lifeos.ui.app import LifeOS
    from lifeos.ui import appearance

    directory = Path(sys.argv[1]).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    app = LifeOS(Database(directory / 'scroll.sqlite3'))
    errors = []
    app.report_callback_exception = lambda exc, value, tb: errors.append(str(value))
    results = {}
    try:
        for i in range(80):
            app.service.save('problems', dict(name=f'Scroll profile {i}', topic='Arrays'))
        app.show('DSA Tracker')
        app.update()
        for theme in (appearance.CURRENT, appearance.COMMAND):
            app.set_theme(theme)
            app.update()
            target = app.record_frames['Problems'].tree
            target.yview('moveto', 0)
            app.update()
            before = app.wallpaper.render_count
            profile = cProfile.Profile()
            timings = []
            offsets = []
            profile.enable()
            for i in range(40):
                started = time.perf_counter()
                target.event_generate('<MouseWheel>', delta=-120 if i < 20 else 120)
                app.update()
                timings.append((time.perf_counter() - started) * 1000)
                offsets.append(target.offset)
            profile.disable()
            assert len(set(offsets)) > 10, 'Expected genuinely overflowing content'
            assert app.wallpaper.render_count == before, 'Wheel repainted the whole window'
            name = 'current' if theme == appearance.CURRENT else 'cmd'
            report = io.StringIO()
            pstats.Stats(profile, stream=report).strip_dirs().sort_stats('cumulative').print_stats(40)
            (directory / (name + '-profile.txt')).write_text(report.getvalue(), encoding='utf-8')
            results[name] = dict(mean_ms=round(sum(timings) / len(timings), 2),
                                 max_ms=round(max(timings), 2), full_repaints=0)
        assert not errors, errors
        results['callback_errors'] = errors
        (directory / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(results))
    finally:
        app.close()
        appearance.select(appearance.CURRENT)


if __name__ == '__main__':
    main()
