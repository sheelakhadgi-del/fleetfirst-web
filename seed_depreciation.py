"""
Seed depreciation periods for all trucks from the Lease Liability Summary tab.

Run:  python seed_depreciation.py

Sources:
- Lease Liabilities and Receivables May 2026 → Summary tab
- VIN → (acq_date, cost_basis, residual) for period 1
- Re-seat trucks get a second DepreciationPeriod at new cost basis

For 1950 ROU trucks: acq_date = Lease Commencement Date, cost = Truck Price + Warranty
For 1504 Purchased: acq_date = Estimated Pick-Up Date, cost = Truck Price + Warranty
For Ryder SN* trucks: acq_date = Lease Commencement Date, cost = initial ROU amount, residual = $51,580
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from app import create_app
from app.models import db, Truck, DepreciationPeriod

app = create_app()

def d(s):
    return datetime.strptime(s, "%m/%d/%Y").date()


# ---------------------------------------------------------------------------
# PERIOD_DATA: VIN (17-char) → list of dicts
#   Each dict: start_date, cost_basis, residual_value, end_date (None=active),
#              notes, asset_account (to update truck if needed)
# ---------------------------------------------------------------------------
PERIOD_DATA = {

    # ── 1950 ROU — Pathway/Ryder Kenworth trucks ────────────────────────────

    # 1Path-R1 / 1Path-R2 / 1Path-R3 (J100045) — re-seat 03/27/2026
    "1XKYDP9X8NJ100045": [
        dict(start=d("04/16/2025"), cost=81500,  residual=15000, end=d("10/03/2025"),
             notes="1Path-R1 John Fisher", acct="1950"),
        dict(start=d("10/03/2025"), cost=76032,  residual=15000, end=d("03/27/2026"),
             notes="1Path-R2 Terry Osby (re-seat)", acct="1950"),
        dict(start=d("03/27/2026"), cost=69308.33, residual=15000, end=None,
             notes="1Path-R3 re-seat 03/27/2026", acct="1950"),
    ],

    # 2Path-R1 / 2Path-R2 / 2Path-R3 (J100040) — re-seat 04/17/2026
    "1XKYDP9X9NJ100040": [
        dict(start=d("04/18/2025"), cost=98500,  residual=15000, end=d("11/04/2025"),
             notes="2Path-R1 Franklin Jones", acct="1950"),
        dict(start=d("11/04/2025"), cost=90266,  residual=15000, end=d("04/17/2026"),
             notes="2Path-R2 Ernesto Pena-Cruz (re-seat)", acct="1950"),
        dict(start=d("04/17/2026"), cost=81800,  residual=15000, end=d("04/17/2026"),
             notes="2Path-R3 re-seat 04/17/2026 ($0 May per schedule)", acct="1950"),
    ],

    # 3Path-R1 / 3Path-S1 (J100031)
    "1XKYDP9X8NJ100031": [
        dict(start=d("04/23/2025"), cost=87500,  residual=15000, end=d("09/29/2025"),
             notes="3Path-R1 Robert Epps", acct="1950"),
        dict(start=d("09/29/2025"), cost=68083.33, residual=5000, end=d("09/29/2025"),
             notes="3Path-S1 Earl Hopkins (re-seat, not in schedule)", acct="1950"),
    ],

    # 4Path-R1 / 4Path-S1 (J227051) — schedule shows 10/31/2025 start only; no P2 yet
    "1XKYD49X8LJ227051": [
        dict(start=d("10/31/2025"), cost=55645.83, residual=5000, end=d("03/09/2026"),
             notes="4Path-R1 Ramano Maben (repo 03/09/2026 per schedule)", acct="1950"),
    ],

    # 5Path-R1 (J489292)
    "1XKYDP9X7NJ489292": [
        dict(start=d("11/21/2025"), cost=57662.50, residual=5000, end=None,
             notes="5Path-R1 Larry Jaramillo (per schedule 11/21/2025)", acct="1950"),
    ],

    # 6Path-R1 (J422698)
    "1XKYDP9X1LJ422698": [
        dict(start=d("08/31/2025"), cost=53953.33, residual=5000, end=None,
             notes="6Path-R1 Chanston Camper (per schedule 8/31/2025)", acct="1950"),
    ],

    # 7Path-R1 (J396131)
    "1XKYDP9X2MJ396131": [
        dict(start=d("10/31/2025"), cost=52205, residual=5000, end=None,
             notes="7Path-R1 Baldemar Barba (per schedule 10/31/2025)", acct="1950"),
    ],

    # 8Path (J359431)
    "1XKYDP9X7LJ359431": [
        dict(start=d("05/06/2025"), cost=59450,  residual=5000, end=d("05/06/2025"),
             notes="8Path Letravious Murray (not in schedule)", acct="1950"),
    ],

    # 9Path (J396180)
    "1XKYDP9X4MJ396180": [
        dict(start=d("05/15/2025"), cost=54450,  residual=5000, end=d("05/15/2025"),
             notes="9Path Christopher Black (not in schedule)", acct="1950"),
    ],

    # 10Path-R1 / 10Path-R2 (J396183) — re-seat 02/20/2026
    "1XKYDP9XXMJ396183": [
        dict(start=d("05/22/2025"), cost=57450,  residual=5000, end=d("02/20/2026"),
             notes="10Path-R1 Uldieu Desir", acct="1950"),
        dict(start=d("02/20/2026"), cost=49582.50, residual=5000, end=None,
             notes="10Path-R2 re-seat 02/20/2026", acct="1950"),
    ],

    # 11Path (J396166)
    "1XKYDP9XXMJ396166": [
        dict(start=d("05/23/2025"), cost=65450,  residual=5000, end=d("05/23/2025"),
             notes="11Path Kizzy Bailey (not in schedule)", acct="1950"),
    ],

    # 12Path-R1 / 12Path-R2 / 12Path-R3 (J396149) — re-seat 02/18/2026
    "1XKYDP9XXMJ396149": [
        dict(start=d("05/30/2025"), cost=57450,  residual=5000, end=d("10/14/2025"),
             notes="12Path-R1 Kendrick White", acct="1950"),
        dict(start=d("10/14/2025"), cost=53997,  residual=5000, end=d("02/18/2026"),
             notes="12Path-R2 Jonathan Riley (re-seat)", acct="1950"),
        dict(start=d("02/18/2026"), cost=49582.50, residual=5000, end=None,
             notes="12Path-R3 re-seat 02/18/2026", acct="1950"),
    ],

    # 13Path (J396161)
    "1XKYDP9X0MJ396161": [
        dict(start=d("06/02/2025"), cost=61450,  residual=5000, end=d("06/02/2025"),
             notes="13Path Melvin Dorsey (not in schedule)", acct="1950"),
    ],

    # 14Path-R1 / 14Path-S1 (J396173)
    "1XKYDP9X7MJ396173": [
        dict(start=d("06/02/2025"), cost=57450,  residual=5000, end=d("11/11/2025"),
             notes="14Path-R1 Gerald Willis", acct="1950"),
        dict(start=d("11/11/2025"), cost=53137,  residual=5000, end=d("11/11/2025"),
             notes="14Path-S1 Kenbert Johnson (re-seat, not in schedule)", acct="1950"),
    ],

    # 15Path (purchased — J462053)
    "1XKYDP9XXMJ462053": [
        dict(start=d("06/10/2025"), cost=57450,  residual=5000, end=d("06/10/2025"),
             notes="15Path Kevin Nelson (not in schedule)", acct="1504"),
    ],

    # 16Path-R1 (J396082)
    "1XKYDP9X4MJ396082": [
        dict(start=d("09/30/2025"), cost=50220, residual=5000, end=None,
             notes="16Path-R1 Casey Briggs (per schedule 9/30/2025)", acct="1504"),
    ],

    # 17Path (J396140)
    "1XKYDP9X3MJ396140": [
        dict(start=d("06/19/2025"), cost=54450,  residual=5000, end=d("06/19/2025"),
             notes="17Path Markee Pippiens (not in schedule)", acct="1504"),
    ],

    # 18Path (J452806)
    "1XKYDP9X5MJ452806": [
        dict(start=d("06/19/2025"), cost=49700,  residual=5000, end=d("06/19/2025"),
             notes="18Path Lamar White (not in schedule)", acct="1504"),
    ],

    # 19Path-R1 / 19Path-R2 (J436689) — re-seat 02/02/2026
    "1XKYDP9X2MJ436689": [
        dict(start=d("06/27/2025"), cost=57450,  residual=5000, end=d("02/02/2026"),
             notes="19Path-R1 Kareem Waller", acct="1504"),
        dict(start=d("02/02/2026"), cost=50456.67, residual=5000, end=None,
             notes="19Path-R2 re-seat 02/02/2026", acct="1504"),
    ],

    # 20Path-R1 / 20Path-R2 / 20Path-R3 (J436710) — re-seat 12/08/2025, re-seat 04/15/2026
    "1XKYDP9X0MJ436710": [
        dict(start=d("06/30/2025"), cost=57450,  residual=5000, end=d("12/08/2025"),
             notes="20Path-R1 Nelson Johnson", acct="1504"),
        dict(start=d("12/08/2025"), cost=52322,  residual=5000, end=d("04/15/2026"),
             notes="20Path-R2 Keith Baker (re-seat)", acct="1504"),
        dict(start=d("04/15/2026"), cost=48708.33, residual=5000, end=None,
             notes="20Path-R3 re-seat 04/15/2026", acct="1504"),
    ],

    # 21Path-R1 / 21Path-R2 / 21Path-R3 (J452805) — re-seat 04/16/2026
    "1XKYDP9X3MJ452805": [
        dict(start=d("06/30/2025"), cost=48000,  residual=5000, end=d("10/08/2025"),
             notes="21Path-R1 David Briggs", acct="1504"),
        dict(start=d("10/08/2025"), cost=45169,  residual=5000, end=d("04/16/2026"),
             notes="21Path-R2 Derrick Barnes (re-seat)", acct="1504"),
        dict(start=d("04/16/2026"), cost=40116.67, residual=5000, end=d("04/16/2026"),
             notes="21Path-R3 re-seat 04/16/2026 ($0 May per schedule)", acct="1504"),
    ],

    # 22Path-R1 (J452808) — repo'd 10/30/2025, no re-seat as of May 2026
    "1XKYDP9X9MJ452808": [
        dict(start=d("08/31/2025"), cost=43190,  residual=5000, end=d("10/30/2025"),
             notes="22Path-R1 James Crittenden (repo 10/30/2025)", acct="1504"),
    ],

    # 23Path-R1 (J396168)
    "1XKYDP9X3MJ396168": [
        dict(start=d("10/01/2025"), cost=47702.50, residual=5000, end=None,
             notes="23Path-R1 Donnie Stanford (per schedule 10/01/2025)", acct="1504"),
    ],

    # 24Path-R1 / 24Path-S1 (J396152)
    "1XKYDP9XXMJ396152": [
        dict(start=d("07/07/2025"), cost=59950,  residual=5000, end=d("12/08/2025"),
             notes="24Path-R1 Lynn Barksdale", acct="1504"),
        dict(start=d("12/08/2025"), cost=54592,  residual=5000, end=d("12/08/2025"),
             notes="24Path-S1 Aaron Hodgden (re-seat, not in schedule)", acct="1504"),
    ],

    # 25Path (J396116)
    "1XKYDP9X6MJ396116": [
        dict(start=d("07/03/2025"), cost=61450,  residual=5000, end=d("07/03/2025"),
             notes="25Path Kenneth Jones (not in schedule)", acct="1504"),
    ],

    # 26Path-R1 / 26Path-S1 (J462684)
    "1XKYDP9XXNJ462684": [
        dict(start=d("07/07/2025"), cost=68050,  residual=5000, end=d("01/20/2026"),
             notes="26Path-R1 Marquita Smith", acct="1504"),
        dict(start=d("01/20/2026"), cost=60904,  residual=5000, end=d("01/20/2026"),
             notes="26Path-S1 Phillip Sampley (re-seat, not in schedule)", acct="1504"),
    ],

    # 27Path (J462748)
    "1XKYDP9XXNJ462748": [
        dict(start=d("07/07/2025"), cost=68050,  residual=5000, end=d("07/07/2025"),
             notes="27Path Clinton Hardy (not in schedule)", acct="1504"),
    ],

    # 28Path-R1 / 28Path-S1 (J396163)
    "1XKYDP9X4MJ396163": [
        dict(start=d("07/08/2025"), cost=57550,  residual=5000, end=d("12/22/2025"),
             notes="28Path-R1 Jerry Stockstill", acct="1504"),
        dict(start=d("12/22/2025"), cost=52426,  residual=5000, end=d("12/22/2025"),
             notes="28Path-S1 Bobby Mcdaniel (re-seat, not in schedule)", acct="1504"),
    ],

    # 29Path (J396142)
    "1XKYDP9X7MJ396142": [
        dict(start=d("07/08/2025"), cost=61550,  residual=5000, end=d("07/08/2025"),
             notes="29Path Kevin Zelie (not in schedule)", acct="1504"),
    ],

    # 30Path-R1 / 30Path-S1 (J462682) — re-seat 01/14/2026
    "1XKYDP9X6NJ462682": [
        dict(start=d("07/08/2025"), cost=68050,  residual=5000, end=d("01/14/2026"),
             notes="30Path-R1 Darnell Ewing", acct="1504"),
        dict(start=d("01/14/2026"), cost=61745,  residual=5000, end=None,
             notes="30Path-S1 re-seat 01/14/2026", acct="1504"),
    ],

    # 31Path-R1 / 31Path-S1 (J462683) — re-seat 11/19/2025
    "1XKYDP9X8NJ462683": [
        dict(start=d("07/09/2025"), cost=68050,  residual=5000, end=d("11/19/2025"),
             notes="31Path-R1 Corey Rushing", acct="1504"),
        dict(start=d("11/19/2025"), cost=62795.83, residual=5000, end=None,
             notes="31Path-S1 re-seat 11/19/2025", acct="1504"),
    ],

    # 32Path-R1 / 32Path-S1 / 32Path-S2 (J462670) — re-seat 10/30/2025, re-seat 05/07/2026
    "1XKYDP9XXNJ462670": [
        dict(start=d("07/14/2025"), cost=68050,  residual=5000, end=d("10/30/2025"),
             notes="32Path-R1 Karisha Williams", acct="1504"),
        dict(start=d("10/30/2025"), cost=63899,  residual=5000, end=d("05/07/2026"),
             notes="32Path-S1 Curtis Brewer (re-seat)", acct="1504"),
        dict(start=d("05/07/2026"), cost=57541.67, residual=5000, end=None,
             notes="32Path-S2 re-seat 05/07/2026 (active per schedule, May=$875.69)", acct="1504"),
    ],

    # 33Path-R1 / 33Path-S1 (J462690)
    "1XKYDP9X5NJ462690": [
        dict(start=d("07/15/2025"), cost=68050,  residual=5000, end=d("09/29/2025"),
             notes="33Path-R1 Alzabian Savage", acct="1504"),
        dict(start=d("09/29/2025"), cost=65948,  residual=5000, end=d("09/29/2025"),
             notes="33Path-S1 Colton Baker (re-seat, not in schedule)", acct="1504"),
    ],

    # 34Path-R1 / 34Path-S1 (J462712)
    "1XKYDP9X0NJ462712": [
        dict(start=d("07/15/2025"), cost=68050,  residual=5000, end=d("12/04/2025"),
             notes="34Path-R1 Leroy Johnson", acct="1504"),
        dict(start=d("12/04/2025"), cost=62901,  residual=5000, end=d("12/04/2025"),
             notes="34Path-S1 Jamond Davis (re-seat, not in schedule)", acct="1504"),
    ],

    # 35Path-R1 / 35Path-S1 (J462701) — re-seat 03/04/2026
    "1XKYDP9X6NJ462701": [
        dict(start=d("07/15/2025"), cost=68050,  residual=5000, end=d("03/04/2026"),
             notes="35Path-R1 Shalako Simon", acct="1504"),
        dict(start=d("03/04/2026"), cost=59643.33, residual=5000, end=None,
             notes="35Path-S1 re-seat 03/04/2026", acct="1504"),
    ],

    # 36Path-R1 (J396061) — per depreciation schedule: start 12/15/2025
    "1XKYDP9X7MJ396061": [
        dict(start=d("12/15/2025"), cost=48175,  residual=5000, end=None,
             notes="36Path-R1 Marcus Thompson", acct="1504"),
    ],

    # 37Path-R1 / 37Path-R2 / 37Path-R3 (J452796) — re-seat 04/24/2026
    "1XKYDP9X6MJ452796": [
        dict(start=d("07/18/2025"), cost=47500,  residual=5000, end=d("12/03/2025"),
             notes="37Path-R1 Toni Brown", acct="1504"),
        dict(start=d("12/03/2025"), cost=44029,  residual=5000, end=d("04/24/2026"),
             notes="37Path-R2 Calvin Breeland Jr (re-seat)", acct="1504"),
        dict(start=d("04/24/2026"), cost=40416.67, residual=5000, end=d("04/24/2026"),
             notes="37Path-R3 re-seat 04/24/2026 ($0 May per schedule)", acct="1504"),
    ],

    # 38Path (J235171) — Pathway lease (1950)
    "1XKYDP9X4PJ235171": [
        dict(start=d("07/11/2025"), cost=68500,  residual=5000, end=d("07/11/2025"),
             notes="38Path Brent Tyrrell (not in schedule)", acct="1950"),
    ],

    # 39Path (J396138)
    "1XKYDP9X5MJ396138": [
        dict(start=d("07/24/2025"), cost=61550,  residual=5000, end=d("07/24/2025"),
             notes="39Path Willie Jackson (not in schedule)", acct="1504"),
    ],

    # 40Path (J462723)
    "1XKYDP9X5NJ462723": [
        dict(start=d("07/28/2025"), cost=68050,  residual=5000, end=d("07/28/2025"),
             notes="40Path Mark Evans (not in schedule)", acct="1504"),
    ],

    # 41Path-R1 (J399485)
    "1XKYDP9X8MJ399485": [
        dict(start=d("08/05/2025"), cost=56800,  residual=5000, end=d("03/09/2026"),
             notes="41Path-R1 Pedro Pena Garcia (repo 03/09/2026)", acct="1504"),
        dict(start=d("03/10/2026"), cost=49893.33, residual=5000, end=None,
             notes="41Path-S1 re-seat 03/10/2026 (per schedule)", acct="1504"),
    ],

    # 42Path-R1 / 42Path-S1 (J462676)
    "1XKYDP9X0NJ462676": [
        dict(start=d("08/22/2025"), cost=68050,  residual=5000, end=d("11/11/2025"),
             notes="42Path-R1 Corey Moore", acct="1504"),
        dict(start=d("11/11/2025"), cost=63899,  residual=5000, end=d("11/11/2025"),
             notes="42Path-S1 Ali Reynolds (re-seat, not in schedule)", acct="1504"),
    ],

    # 43Path (J462768)
    "1XKYDP9X5NJ462768": [
        dict(start=d("08/20/2025"), cost=68050,  residual=5000, end=d("08/20/2025"),
             notes="43Path Jerry Williams (not in schedule)", acct="1504"),
    ],

    # 44Path-R1 / 44Path-S1 (J462714)
    "1XKYDP9X4NJ462714": [
        dict(start=d("08/08/2025"), cost=68050,  residual=5000, end=d("01/16/2026"),
             notes="44Path-R1 Donald Slayback", acct="1504"),
        dict(start=d("01/16/2026"), cost=60904,  residual=5000, end=d("01/16/2026"),
             notes="44Path-S1 Michel Bien-Aime (re-seat, not in schedule)", acct="1504"),
    ],

    # 45Path-R1 / 45Path-R2 / 45Path-R3 (J462760) — re-seat 02/16/2026
    "1XKYDP9X0NJ462760": [
        dict(start=d("08/13/2025"), cost=68050,  residual=5000, end=d("11/07/2025"),
             notes="45Path-R1 Mario Dawson", acct="1504"),
        dict(start=d("11/07/2025"), cost=63899,  residual=5000, end=d("02/16/2026"),
             notes="45Path-R2 Markese Smith (re-seat)", acct="1504"),
        dict(start=d("02/16/2026"), cost=59643.33, residual=5000, end=None,
             notes="45Path-R3 re-seat 02/16/2026", acct="1504"),
    ],

    # 46Path / 46Path-S1 (J462751) — re-seat 05/26/2026
    "1XKYDP9XXNJ462751": [
        dict(start=d("08/18/2025"), cost=68050,  residual=5000, end=d("05/26/2026"),
             notes="46Path Henry Covington", acct="1504"),
        dict(start=d("05/26/2026"), cost=56490.83, residual=5000, end=None,
             notes="46Path-S1 re-seat 05/26/2026", acct="1504"),
    ],

    # 47Path-R1 / 47Path-S1 (J462699) — re-seat 11/11/2025
    "1XKYDP9X1NJ462699": [
        dict(start=d("08/05/2025"), cost=68050,  residual=5000, end=d("11/11/2025"),
             notes="47Path-R1 Brian Taylor", acct="1504"),
        dict(start=d("11/11/2025"), cost=63846.67, residual=5000, end=None,
             notes="47Path-S1 re-seat 11/11/2025", acct="1504"),
    ],

    # 48Path-R1 (J462724)
    "1XKYDP9X7NJ462724": [
        dict(start=d("08/18/2025"), cost=68050,  residual=5000, end=d("02/04/2026"),
             notes="48Path-R1 Michael Stafford (repo 02/04/2026)", acct="1504"),
        dict(start=d("02/05/2026"), cost=60694.17, residual=5000, end=None,
             notes="48Path-S1 re-seat 02/05/2026 (per schedule)", acct="1504"),
    ],

    # 49Path (J462740)
    "1XKYDP9X5NJ462740": [
        dict(start=d("08/04/2025"), cost=68050,  residual=5000, end=d("08/04/2025"),
             notes="49Path Joey Dunbar (not in schedule)", acct="1504"),
    ],

    # 50Path-R1 / 50Path-S1 (J462704)
    "1XKYDP9X1NJ462704": [
        dict(start=d("08/13/2025"), cost=68050,  residual=5000, end=d("12/18/2025"),
             notes="50Path-R1 James Dandridge", acct="1504"),
        dict(start=d("12/18/2025"), cost=61903,  residual=5000, end=d("12/18/2025"),
             notes="50Path-S1 Dwight Lee (re-seat, not in schedule)", acct="1504"),
    ],

    # 51Path-R1 / 51Path-S1 (J462739) — re-seat 11/19/2025
    "1XKYDP9X9NJ462739": [
        dict(start=d("08/11/2025"), cost=68050,  residual=5000, end=d("11/19/2025"),
             notes="51Path-R1 Tony Hayes", acct="1504"),
        dict(start=d("11/19/2025"), cost=62795.83, residual=5000, end=None,
             notes="51Path-S1 re-seat 11/19/2025", acct="1504"),
    ],

    # 52Path-R1 (J462732) — re-seated 11/21/2025, repo'd 01/19/2026, no re-seat
    "1XKYDP9X6NJ462732": [
        dict(start=d("11/21/2025"), cost=62795.83, residual=5000, end=d("01/19/2026"),
             notes="52Path-R1 Elmore Spooney (repo 01/19/2026)", acct="1504"),
    ],

    # ── 1950 ROU — Ryder trucks (SN* IDs) — corrected from depreciation schedule ──
    # Residual $51,580 unless noted. SNT5098 residual is $5,000 (not Ryder standard).

    # SNM2149 — not in current depreciation schedule; close out
    "SNM2149": [
        dict(start=d("09/30/2025"), cost=81682, residual=51580, end=d("09/30/2025"),
             notes="SNM2149 closed (not in schedule)", acct="1950"),
    ],
    "SNJ6200": [
        dict(start=d("09/04/2025"), cost=85966, residual=51580, end=d("12/11/2025"),
             notes="74Path Ryder ROU (repo 12/11/2025)", acct="1950"),
    ],
    "SNR9898": [
        dict(start=d("09/15/2025"), cost=85966, residual=51580, end=d("10/15/2025"),
             notes="73Path-R1 Ryder ROU P1 (repo 10/15/2025)", acct="1950"),
        dict(start=d("01/21/2026"), cost=79218.83, residual=51580, end=None,
             notes="73Path-R1 Ryder ROU re-seat 01/21/2026", acct="1950"),
    ],
    "SNN2805": [
        dict(start=d("09/26/2025"), cost=85966, residual=51580, end=None,
             notes="76Path Ryder ROU", acct="1950"),
    ],
    "SNT5098": [
        dict(start=d("11/02/2025"), cost=84616.57, residual=5000, end=None,
             notes="67Path-R1 Ryder ROU (residual $5,000)", acct="1950"),
    ],
    "SNH2987": [
        dict(start=d("12/02/2025"), cost=84246.70, residual=51580, end=None,
             notes="65Path-R1 Ryder ROU", acct="1950"),
    ],
    "SNR9971": [
        dict(start=d("12/01/2025"), cost=84246.70, residual=51580, end=None,
             notes="70Path-R1 Ryder ROU", acct="1950"),
    ],
    "SNM2134": [
        dict(start=d("02/09/2026"), cost=83100.47, residual=51580, end=None,
             notes="77Path-R1 Ryder ROU", acct="1950"),
    ],
    "SNP1655": [
        dict(start=d("03/27/2026"), cost=81954.30, residual=51580, end=None,
             notes="66Path-R1 Ryder ROU", acct="1950"),
    ],
    "SNB7372": [
        dict(start=d("04/06/2026"), cost=81954.30, residual=51580, end=None,
             notes="78Path-R1 Ryder ROU", acct="1950"),
    ],

    # ── Additional 1504 trucks from depreciation schedule ────────────────────

    # J396139 — start 09/25/2025, active
    "1XKYDP9X7MJ396139": [
        dict(start=d("09/25/2025"), cost=50550, residual=5000, end=None,
             notes="J396139 re-seat 09/25/2025", acct="1504"),
    ],
    # J451222 — start 12/16/2025, active
    "1XKYDP9X7MJ451222": [
        dict(start=d("12/16/2025"), cost=48913.33, residual=5000, end=None,
             notes="J451222 re-seat 12/16/2025", acct="1504"),
    ],
    # J462745 — start 12/17/2025, active
    "1XKYDP9X4NJ462745": [
        dict(start=d("12/17/2025"), cost=62795.83, residual=5000, end=None,
             notes="J462745 re-seat 12/17/2025", acct="1504"),
    ],
    # J462749 — start 12/31/2025, active
    "1XKYDP9X1NJ462749": [
        dict(start=d("12/31/2025"), cost=62795.83, residual=5000, end=None,
             notes="J462749 re-seat 12/31/2025", acct="1504"),
    ],
    # J438187 — start 01/07/2026, active
    "1XKYDP9XXMJ438187": [
        dict(start=d("01/07/2026"), cost=55645.83, residual=5000, end=None,
             notes="J438187 re-seat 01/07/2026", acct="1504"),
    ],
    # J462726 — start 01/14/2026, active
    "1XKYDP9X0NJ462726": [
        dict(start=d("01/14/2026"), cost=62795.83, residual=5000, end=None,
             notes="J462726 re-seat 01/14/2026", acct="1504"),
    ],
    # J462763 — start 01/16/2026, active
    "1XKYDP9X6NJ462763": [
        dict(start=d("01/16/2026"), cost=65750, residual=5000, end=None,
             notes="J462763 re-seat 01/16/2026", acct="1504"),
    ],
    # J462716 — start 01/26/2026, active
    "1XKYDP9X8NJ462716": [
        dict(start=d("01/26/2026"), cost=60694.17, residual=5000, end=None,
             notes="J462716 re-seat 01/26/2026", acct="1504"),
    ],
    # J451208 — repo 11/06/2025; re-seat 02/03/2026
    "1XKYDP9X2MJ451208": [
        dict(start=d("09/11/2025"), cost=47050, residual=5000, end=d("11/06/2025"),
             notes="J451208 P1 (repo 11/06/2025)", acct="1504"),
        dict(start=d("02/03/2026"), cost=50420.83, residual=5000, end=None,
             notes="J451208 re-seat 02/03/2026", acct="1504"),
    ],
    # J451216 — repo 10/14/2025; re-seat 03/02/2026
    "1XKYDP9X1MJ451216": [
        dict(start=d("09/11/2025"), cost=47050, residual=5000, end=d("10/14/2025"),
             notes="J451216 P1 (repo 10/14/2025)", acct="1504"),
        dict(start=d("03/02/2026"), cost=49595, residual=5000, end=None,
             notes="J451216 re-seat 03/02/2026", acct="1504"),
    ],
    # J462680 — repo 12/29/2025; re-seat 02/16/2026
    "1XKYDP9X2NJ462680": [
        dict(start=d("11/11/2025"), cost=64897.50, residual=5000, end=d("12/29/2025"),
             notes="J462680 P1 (repo 12/29/2025)", acct="1504"),
        dict(start=d("02/16/2026"), cost=60694.17, residual=5000, end=None,
             notes="J462680 re-seat 02/16/2026", acct="1504"),
    ],

    # ── Previously missing 1504 trucks (from depreciation schedule) ──────────

    # J396063 — repo 11/17/2025, re-seat 04/16/2026
    "1XKYDP9X0MJ396063": [
        dict(start=d("06/20/2025"), cost=54550, residual=5000, end=d("11/17/2025"),
             notes="J396063 P1 (repo 11/17/2025)", acct="1504"),
        dict(start=d("04/16/2026"), cost=46291.67, residual=5000, end=None,
             notes="J396063 re-seat 04/16/2026", acct="1504"),
    ],
    # J452803 — repo 11/06/2025, re-seat 04/15/2026
    "1XKYDP9XXMJ452803": [
        dict(start=d("06/23/2025"), cost=50800, residual=5000, end=d("11/06/2025"),
             notes="J452803 P1 (repo 11/06/2025)", acct="1504"),
        dict(start=d("04/15/2026"), cost=43930, residual=5000, end=None,
             notes="J452803 re-seat 04/15/2026", acct="1504"),
    ],
    # J452794 — repo 11/03/2025, re-seat 02/12/2026
    "1XKYDP9X2MJ452794": [
        dict(start=d("06/23/2025"), cost=48600, residual=5000, end=d("11/03/2025"),
             notes="J452794 P1 (repo 11/03/2025)", acct="1504"),
        dict(start=d("02/12/2026"), cost=43513.33, residual=5000, end=None,
             notes="J452794 re-seat 02/12/2026", acct="1504"),
    ],
    # J462665 — re-seat 10/28/2025 (active)
    "1XKYDP9X6NJ462665": [
        dict(start=d("10/28/2025"), cost=64897.50, residual=5000, end=None,
             notes="J462665 re-seat 10/28/2025", acct="1504"),
    ],
    # J462729 — repo 10/06/2025, no re-seat
    "1XKYDP9X6NJ462729": [
        dict(start=d("08/08/2025"), cost=60550, residual=5000, end=d("10/06/2025"),
             notes="J462729 (repo 10/06/2025)", acct="1504"),
    ],
    # J462774 — repo 12/08/2025, re-seat 12/08/2025, repo 03/24/2026, re-seat 03/24/2026
    "1XKYDP9X0NJ462774": [
        dict(start=d("08/08/2025"), cost=69000, residual=5000, end=d("12/08/2025"),
             notes="J462774 P1 (repo 12/08/2025)", acct="1504"),
        dict(start=d("12/08/2025"), cost=64733.33, residual=5000, end=d("03/24/2026"),
             notes="J462774 P2 (repo 03/24/2026)", acct="1504"),
        dict(start=d("03/24/2026"), cost=60466.67, residual=5000, end=None,
             notes="J462774 re-seat 03/24/2026", acct="1504"),
    ],
    # J462766 — repo 10/20/2025, no re-seat
    "1XKYDP9X1NJ462766": [
        dict(start=d("08/08/2025"), cost=69500, residual=5000, end=d("10/20/2025"),
             notes="J462766 (repo 10/20/2025)", acct="1504"),
    ],
    # J462761 — re-seat 01/13/2026 (active)
    "1XKYDP9X2NJ462761": [
        dict(start=d("01/13/2026"), cost=55920.83, residual=5000, end=None,
             notes="J462761 re-seat 01/13/2026", acct="1504"),
    ],
    # J462710 — repo 10/07/2025, re-seat 04/16/2026
    "1XKYDP9X7NJ462710": [
        dict(start=d("08/15/2025"), cost=60550, residual=5000, end=d("10/07/2025"),
             notes="J462710 P1 (repo 10/07/2025)", acct="1504"),
        dict(start=d("04/16/2026"), cost=58592.50, residual=5000, end=d("04/16/2026"),
             notes="J462710 re-seat 04/16/2026 ($0 May per schedule)", acct="1504"),
    ],
    # J462707 — repo 10/01/2025, no re-seat
    "1XKYDP9X7NJ462707": [
        dict(start=d("08/15/2025"), cost=60550, residual=5000, end=d("10/01/2025"),
             notes="J462707 (repo 10/01/2025)", acct="1504"),
    ],
    # J462755 — repo 12/15/2025, no re-seat
    "1XKYDP9X7NJ462755": [
        dict(start=d("11/18/2025"), cost=65135, residual=5000, end=d("12/15/2025"),
             notes="J462755 (repo 12/15/2025)", acct="1504"),
    ],
    # J396156 — repo ~10/15/2025, re-seat 05/22/2026
    "1XKYDP9X7MJ396156": [
        dict(start=d("08/19/2025"), cost=46050, residual=5000, end=d("10/15/2025"),
             notes="J396156 P1 (repo 10/15/2025)", acct="1504"),
        dict(start=d("05/22/2026"), cost=46267.50, residual=5000, end=None,
             notes="J396156 re-seat 05/22/2026", acct="1504"),
    ],
    # J396176 — repo 11/18/2025, no re-seat
    "1XKYDP9X2MJ396176": [
        dict(start=d("08/19/2025"), cost=50050, residual=5000, end=d("11/18/2025"),
             notes="J396176 (repo 11/18/2025)", acct="1504"),
    ],
    # J396178 — repo 01/26/2026, re-seat 05/04/2026
    "1XKYDP9X6MJ396178": [
        dict(start=d("12/13/2025"), cost=62522.50, residual=5000, end=d("01/26/2026"),
             notes="J396178 P1 (repo 01/26/2026)", acct="1504"),
        dict(start=d("05/04/2026"), cost=57476.67, residual=5000, end=None,
             notes="J396178 re-seat 05/04/2026", acct="1504"),
    ],
    # J462769 — repo 02/04/2026, re-seat 03/05/2026
    "1XKYDP9X7NJ462769": [
        dict(start=d("08/20/2025"), cost=67500, residual=5000, end=d("02/04/2026"),
             notes="J462769 P1 (repo 02/04/2026)", acct="1504"),
        dict(start=d("03/05/2026"), cost=61250, residual=5000, end=None,
             notes="J462769 re-seat 03/05/2026", acct="1504"),
    ],
    # J462671 — repo 11/05/2025, re-seat 02/12/2026
    "1XKYDP9X1NJ462671": [
        dict(start=d("08/20/2025"), cost=67500, residual=5000, end=d("11/05/2025"),
             notes="J462671 P1 (repo 11/05/2025)", acct="1504"),
        dict(start=d("02/12/2026"), cost=62291.67, residual=5000, end=None,
             notes="J462671 re-seat 02/12/2026", acct="1504"),
    ],
    # J462691 — repo 10/22/2025, re-seat 04/09/2026
    "1XKYDP9X7NJ462691": [
        dict(start=d("08/20/2025"), cost=67500, residual=5000, end=d("10/22/2025"),
             notes="J462691 P1 (repo 10/22/2025)", acct="1504"),
        dict(start=d("04/09/2026"), cost=60208.33, residual=5000, end=None,
             notes="J462691 re-seat 04/09/2026", acct="1504"),
    ],
    # J462767 — repo 11/04/2025, re-seat 04/09/2026
    "1XKYDP9X3NJ462767": [
        dict(start=d("08/20/2025"), cost=69500, residual=5000, end=d("11/04/2025"),
             notes="J462767 P1 (repo 11/04/2025)", acct="1504"),
        dict(start=d("04/09/2026"), cost=61975, residual=5000, end=None,
             notes="J462767 re-seat 04/09/2026", acct="1504"),
    ],
    # J396055 — repo 10/20/2025, re-seat 04/21/2026
    "1XKYDP9X1MJ396055": [
        dict(start=d("08/25/2025"), cost=47050, residual=5000, end=d("10/20/2025"),
             notes="J396055 P1 (repo 10/20/2025)", acct="1504"),
        dict(start=d("04/21/2026"), cost=47943.33, residual=5000, end=None,
             notes="J396055 re-seat 04/21/2026", acct="1504"),
    ],
    # J396079 — repo 10/27/2025, no re-seat
    "1XKYDP9X4MJ396079": [
        dict(start=d("08/28/2025"), cost=47050, residual=5000, end=d("10/27/2025"),
             notes="J396079 (repo 10/27/2025)", acct="1504"),
    ],
    # J462727 — repo 01/29/2026, re-seat 03/31/2026
    "1XKYDP9X2NJ462727": [
        dict(start=d("12/11/2025"), cost=64660, residual=5000, end=d("01/29/2026"),
             notes="J462727 P1 (repo 01/29/2026)", acct="1504"),
        dict(start=d("03/31/2026"), cost=60473.33, residual=5000, end=None,
             notes="J462727 re-seat 03/31/2026", acct="1504"),
    ],
    # J462715 — repo 10/24/2025, no re-seat
    "1XKYDP9X6NJ462715": [
        dict(start=d("08/28/2025"), cost=60300, residual=5000, end=d("10/24/2025"),
             notes="J462715 (repo 10/24/2025)", acct="1504"),
    ],
    # J462705 — repo 10/29/2025, re-seat 04/01/2026
    "1XKYDP9X3NJ462705": [
        dict(start=d("08/28/2025"), cost=60550, residual=5000, end=d("10/29/2025"),
             notes="J462705 P1 (repo 10/29/2025)", acct="1504"),
        dict(start=d("04/01/2026"), cost=60694.17, residual=5000, end=None,
             notes="J462705 re-seat 04/01/2026", acct="1504"),
    ],
    # J462737 — repo 10/07/2025, re-seat 04/07/2026
    "1XKYDP9X5NJ462737": [
        dict(start=d("08/28/2025"), cost=60550, residual=5000, end=d("10/07/2025"),
             notes="J462737 P1 (repo 10/07/2025)", acct="1504"),
        dict(start=d("04/07/2026"), cost=60694.17, residual=5000, end=None,
             notes="J462737 re-seat 04/07/2026", acct="1504"),
    ],
    # J462677 — repo 11/21/2025, re-seat 01/09/2026
    "1XKYDP9X2NJ462677": [
        dict(start=d("08/20/2025"), cost=68500, residual=5000, end=d("11/21/2025"),
             notes="J462677 P1 (repo 11/21/2025)", acct="1504"),
        dict(start=d("01/09/2026"), cost=64266.67, residual=5000, end=None,
             notes="J462677 re-seat 01/09/2026", acct="1504"),
    ],
    # J462730 — repo 03/25/2026, no re-seat
    "1XKYDP9X2NJ462730": [
        dict(start=d("12/17/2025"), cost=65200, residual=5000, end=d("03/25/2026"),
             notes="J462730 (repo 03/25/2026)", acct="1504"),
    ],
    # J462711 — new truck, start 04/13/2026
    "1XKYDP9X9NJ462711": [
        dict(start=d("04/13/2026"), cost=59643.33, residual=5000, end=None,
             notes="J462711 new 04/13/2026", acct="1504"),
    ],

    # J396105 — re-seat 11/21/2025 (from depreciation schedule, $711.18/mo)
    "1XKYDP9X1MJ396105": [
        dict(start=d("11/21/2025"), cost=47670.83, residual=5000, end=None,
             notes="J396105 re-seat 11/21/2025", acct="1504"),
    ],

    # ── J462765 — 2022 Kenworth purchased (from original DB) ─────────────────
    "1XKYDP9X4NJ462765": [
        dict(start=d("02/01/2022"), cost=131900, residual=5000, end=d("02/01/2022"),
             notes="Purchased 2022 (not in May 2026 depreciation schedule)", acct="1504"),
    ],
}


def seed():
    with app.app_context():
        db.create_all()
        trucks = Truck.query.all()

        created = 0
        updated = 0
        skipped = 0
        not_found = 0

        # Remove old incorrect periods for trucks we're going to re-seed
        target_vins = set(PERIOD_DATA.keys())
        existing_trucks = {t.vin: t for t in trucks}

        for vin, periods in PERIOD_DATA.items():
            truck = existing_trucks.get(vin)
            if not truck:
                # Try lookup by truck_id for short IDs like SNH2987
                truck = Truck.query.filter_by(truck_id=vin).first()
            if not truck:
                # Auto-create the truck record
                is_short_id = len(vin) < 17
                truck_id_val = vin if is_short_id else ("J" + vin[-6:])
                first = periods[0]
                truck = Truck(
                    vin=truck_id_val if is_short_id else vin,
                    truck_id=truck_id_val,
                    asset_account=first["acct"],
                    residual_value=first["residual"],
                    useful_life_months=60,
                    status="AVAILABLE",
                )
                db.session.add(truck)
                db.session.flush()
                existing_trucks[vin] = truck
                print(f"  CREATED  {truck.truck_id or truck.vin}")
                not_found += 1

            # Delete existing periods for this truck so we can re-seed cleanly
            if truck.depreciation_periods:
                for p in truck.depreciation_periods:
                    db.session.delete(p)
                db.session.flush()
                updated += 1

            first = periods[0]
            # Update truck fields from first period
            if not truck.acquisition_date:
                truck.acquisition_date = first["start"]
            if not truck.acquisition_cost:
                truck.acquisition_cost = first["cost"]
            truck.residual_value = first["residual"]
            truck.useful_life_months = 60
            if truck.asset_account != first["acct"]:
                truck.asset_account = first["acct"]

            for p in periods:
                period = DepreciationPeriod(
                    truck_id=truck.id,
                    start_date=p["start"],
                    end_date=p["end"],
                    cost_basis=p["cost"],
                    residual_value=p["residual"],
                    life_months=60,
                    notes=p["notes"],
                )
                db.session.add(period)
                monthly = (p["cost"] - p["residual"]) / 60
                end_str = p["end"].strftime("%m/%d/%y") if p["end"] else "active"
                print(f"  {'UPDATE' if updated else 'OK':6s} {truck.truck_id or truck.vin:15s} "
                      f"{p['start'].strftime('%m/%d/%y')}->{end_str:8s}  "
                      f"cost=${p['cost']:>8,.0f}  mo=${monthly:>7,.2f}  {p['notes'][:40]}")

            created += len(periods)

        db.session.commit()
        print(f"\nDone — {created} periods created/updated across trucks "
              f"({not_found} new truck records auto-created).")


if __name__ == "__main__":
    print("Seeding depreciation periods from Lease Liability Summary tab...\n")
    seed()
