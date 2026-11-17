import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'web'/'app.js').read_text(encoding='utf-8')


def test_only_job_stage_is_a_polite_live_region():
    panel=re.search(r'<section id="progress-panel"[^>]*>',HTML).group(0)
    stage=re.search(r'<h2 id="job-stage"[^>]*>',HTML).group(0)
    assert 'aria-live' not in panel, f'progress panel is still a live region: {panel}'
    assert 'aria-live="polite"' in stage, f'job stage is not a polite live region: {stage}'
    for id_ in ('percent','progress-note','progress'):
        tag=re.search(rf'<[a-z]+ [^>]*id="{id_}"[^>]*>',HTML).group(0)
        assert 'aria-live' not in tag, f'{id_} must stay visual-only: {tag}'


def test_show_updates_job_stage_on_every_poll():
    assert re.search(r"\$\('job-stage'\)\.textContent=job\.stage", JS), "show() does not update #job-stage from job.stage"
