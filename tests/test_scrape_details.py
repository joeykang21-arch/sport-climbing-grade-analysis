"""Tests for the climb-page parsers, pinned to the live site's current markup.

These fixtures reproduce the two layout changes that broke the boulder repo's
scraper (PLAN.md 0.2-0.4): the ascent count followed by an unsuccessful-attempt
clause, the blank leading column in the ascents table with DNF rows mixed in,
and the navigation dropdown rendered inside the ``<h1>``.
"""

from bs4 import BeautifulSoup

from sportgradehistory.scrape_details import parse_ascents, parse_header

CLIMB_PAGE = """
<h1><div class="climb-title-row">
  <span>Rainman <small class="fw-normal">| 9b Sport route at
        <a href="/crag/610/malham-cove">Malham Cove</a></small></span>
  <span><div class="dropdown">
    <button class="btn dropdown-toggle">More</button>
    <ul class="dropdown-menu">
      <li><a href="/changes?climb_id=4">Change Log</a></li>
      <li><a href="/notes-log?climb_id=4">Notes Log</a></li>
      <li><a href="/threads?climb_id=4">Threads</a></li>
    </ul></div></span>
</div></h1>
<h2>Ascents</h2>
<p>3 successful ascents and 1 unsuccessful attempt recorded.</p>
<table>
  <thead><tr><th></th><th>Climber</th><th>Style</th><th>Ascent Date</th>
             <th>Suggested Grade</th></tr></thead>
  <tbody>
    <tr class="ascent dnf collapsible-row"><td></td><td>A. Attempter</td>
        <td>Lead | did not finish</td><td></td><td></td></tr>
    <tr class="ascent ascent-detail-row dnf"><td></td>
        <td colspan="4">References [1] somewhere</td></tr>
    <tr class="ascent collapsible-row"><td></td>
        <td><a href="/climber/1">Steve McClure</a></td>
        <td>Lead | worked</td><td>4th Jun 2017</td><td>9b</td></tr>
    <tr class="ascent ascent-subtitle-row"><td></td>
        <td colspan="4">First ascent. 127 sessions.</td></tr>
    <tr class="ascent collapsible-row"><td></td><td>Eder Lomba</td>
        <td>Lead | worked</td><td>13th May 2022</td><td>9b</td></tr>
  </tbody>
</table>
"""

UNGRADED_PAGE = """
<h1><div class="climb-title-row">
  <span>Southeast Ridge <small>| Mt. Everest</small></span>
  <span><div class="dropdown"><button>More</button>
    <ul><li><a href="/changes?climb_id=2627">Change Log</a></li>
        <li><a href="/notes-log?climb_id=2627">Notes Log</a></li>
        <li><a href="/threads?climb_id=2627">Threads</a></li></ul>
  </div></span>
</div></h1>
<p>2 successful ascents recorded.</p>
"""


def _soup(html):
    return BeautifulSoup(html, "html.parser")


def test_parse_header_drops_the_nav_dropdown():
    header = parse_header(_soup(CLIMB_PAGE))
    assert header == {
        "climb_name": "Rainman",
        "grade": "9b",
        "climb_type": "Sport route",
        "location": "Malham Cove",
    }


def test_parse_header_ungraded_route_shifts_as_documented():
    # Defect 3 in the making: no grade in the heading, so positional parsing
    # misreads the location. The raw scrape records it this way on purpose --
    # clean.clean_detail_frame is the repair.
    header = parse_header(_soup(UNGRADED_PAGE))
    assert header["climb_name"] == "Southeast Ridge"
    assert header["grade"] == "Mt."
    assert header["climb_type"] == "Everest"
    assert header["location"] is None


def test_parse_ascents_reads_count_with_unsuccessful_clause():
    # "recorded" no longer follows "ascents"; requiring it parses everything
    # as zero and keeps no rows at all.
    assert parse_ascents(_soup(CLIMB_PAGE))["num_ascents"] == 3


def test_parse_ascents_skips_dnf_and_subrows_and_survives_leading_column():
    ascents = parse_ascents(_soup(CLIMB_PAGE))
    # Not the DNF, not the subtitle row, and every field on its own column
    # despite the blank expand-toggle column at index 0.
    assert ascents["first_climber"] == "Steve McClure"
    assert ascents["first_style"] == "Lead | worked"
    assert ascents["first_ascent_date"] == "4th Jun 2017"
    assert ascents["first_suggested_grade"] == "9b"


def test_parse_ascents_plain_count_still_works():
    assert parse_ascents(_soup(UNGRADED_PAGE))["num_ascents"] == 2
