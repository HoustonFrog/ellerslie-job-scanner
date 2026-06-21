POSITIVE_KEYWORDS = [
    "accountant",
    "accounts payable",
    "accounts receivable",
    "bookkeeper",
    "finance officer",
    "management accountant",
    "financial controller",
    "tax accountant",
    "payroll",
    "audit",
    "finance analyst",
    "fp&a",
    "finance business partner",
    "treasury",
    "credit controller",
    "finance manager",
]

AGENCY_BLOCKLIST = [
    "hays",
    "robert half",
    "michael page",
    "randstad",
    "hudson",
    "adecco",
    "manpowergroup",
    "robert walters",
    "frog recruitment",
    "beyond recruitment",
    "madison",
    "ocg consulting",
    "talent solutions",
    "momentum",
    "potentia",
    "people2people",
    "chandler macleod",
    "drake",
    "kelly services",
    "page personnel",
    "accountancy recruitment",
    "hunter campbell",
    "tyler wren",
    "alexander james",
    "awf group",
    "converge",
    "absolute it",
    "hayes",
    "talent international",
    "seek",
    "recruit",
    "staffing",
    "employment",
    "personnel",
]

SEARCH_KEYWORD_GROUPS = [
    "accounting",
    "accounts payable OR accounts receivable",
    "bookkeeper OR payroll",
    "finance analyst OR finance business partner",
    "financial controller OR treasury OR audit",
    "finance manager",
]

LOCATION_TARGETS = [
    "Ellerslie+Auckland",
    "Greenlane+Auckland",
    "Remuera+Auckland",
    "Penrose+Auckland",
    "Mt+Wellington+Auckland",
    "Newmarket+Auckland",
    "Epsom+Auckland",
    "One+Tree+Hill+Auckland",
]

LOCATION_ALLOW = [
    "ellerslie", "greenlane", "remuera",
    "penrose", "mt wellington", "mount wellington",
    "newmarket", "epsom", "one tree hill", "onehunga",
]

LOCATION_PROXIMITY = {
    "ellerslie": 5,
    "greenlane": 4,
    "remuera": 4,
    "penrose": 3,
    "mt wellington": 3,
    "mount wellington": 3,
    "one tree hill": 4,
    "onehunga": 2,
    "newmarket": 3,
    "epsom": 3,
}

LOCATION_REJECT = [
    "cbd", "central auckland", "city centre",
    "north shore", "northcote", "takapuna", "albany", "rosedale", "browns bay",
    "manukau", "botany", "howick", "pakuranga", "east tamaki", "flat bush",
    "henderson", "new lynn", "te atatu", "west auckland",
    "papakura", "pukekohe", "south auckland",
    "hamilton", "wellington", "christchurch", "tauranga", "dunedin", "queenstown",
    "remote",
]

SEEK_SEARCH_TEMPLATE = "https://www.seek.co.nz/jobs?keywords={keyword}&where={location}&daterange=14"
LINKEDIN_SEARCH_TEMPLATE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={keyword}&location=Auckland%2C+New+Zealand&f_TPR=r1209600&start={start}"
LINKEDIN_REQUEST_DELAY = 3

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 15

SCORE_WEIGHTS = {
    "proximity": 0.30,
    "relevance": 0.20,
    "experience": 0.15,
    "company": 0.15,
    "salary": 0.10,
    "stability": 0.10,
}

JOB_TYPE_STYLES = {
    "full-time": {"bg": "#dbeafe", "fg": "#1e40af", "label": "Full-time"},
    "part-time": {"bg": "#ede9fe", "fg": "#5b21b6", "label": "Part-time"},
    "casual":    {"bg": "#fef9c4", "fg": "#854d0e", "label": "Casual"},
    "contract":  {"bg": "#fce7f3", "fg": "#9d174d", "label": "Contract/Temp"},
    "unknown":   {"bg": "#f3f4f6", "fg": "#374151", "label": "Unknown"},
}
