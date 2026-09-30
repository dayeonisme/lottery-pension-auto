import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from monthly_report import previous_month, summarize, format_report, KST


def row(t, dt, no, result, rank='-', prize='-'):
    return [t, dt, '1', str(no), 'x', '1000', '2026-08-01', result, rank, prize, '-']


def test_previous_month():
    assert previous_month(datetime(2026, 1, 1, 10, tzinfo=KST)) == '2025-12'
    assert previous_month(datetime(2026, 9, 1, 10, tzinfo=KST)) == '2026-08'


def test_summarize_and_format():
    rows = [row('로또6/45', '2026-08-03 10:00:00', i, 'no prize') for i in range(1, 5)]
    rows.append(row('로또6/45', '2026-08-03 10:00:00', 5, 'win', '5등', '5000'))
    rows.append(row('연금복권720+', '2026-08-07 10:00:00', 1, 'win', '7등', '1000'))
    rows.append(row('연금복권720+', '2026-08-07 10:00:00', 2, 'win', '7등', '1,000'))
    rows.append(row('로또6/45', '2026-09-01 10:00:00', 1, 'pending'))  # 다른 달
    s = summarize(rows, '2026-08')
    assert s['로또6/45']['tickets'] == 5 and s['로또6/45']['sessions'] == 1
    assert s['로또6/45']['prize'] == 5000 and s['로또6/45']['ranks'] == {'5등': 1}
    assert s['연금복권720+']['ranks'] == {'7등': 2} and s['연금복권720+']['prize'] == 2000
    msg = format_report('2026-08', s)
    assert '2026년 8월 결산' in msg and '7,000원' in msg and '5등: 1건' in msg
