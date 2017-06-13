import collections

CITIES = [
    'manhattan-ny',
    'brooklyn-ny',
    'bronx-ny',
    'boston-ma',
    'queens-ny',
    'portland-or',
    'tacoma-wa',
    'seattle-wa',
    'chicago-il',
    'philadelphia-pa',
    'los-angeles-ca',
    'san-jose-ca',
    'peninsula-ca', #not available from new onboard boundary file
    'atlanta-ga',
    'long-island-ny', #not available from new onboard boundary file
    'dallas-tx',
    'new-orleans-la',
    'san-francisco-ca',
    'fort-worth-tx',
    'austin-tx',
    'denver-co',
    'washington-dc',
    'staten-island-ny',
]

NEW_YORK_CITY_SLUGS_SET = frozenset(
        (
            'manhattan-ny', 
            'brooklyn-ny', 
            'queens-ny', 
            'bronx-ny', 
            'staten-island-ny'
        )
    )

PSEUDO_CITY_OTHER = {
    'name': "Other",
    'center': {"type": "Point", "coordinates": [-73.96977119534606, 40.77432194861532]},
    'bounds': [-74.034444, 40.679548, -73.907, 40.882214],
    'state': None,
}

DISTANCE_DEFAULTS = {
    'reasonableTravel': {
        'distance': 8046,
        'description': "within 5 miles",
    },
    'area': {
        'distance': 1609,
        'description': "within a mile",
    },
    'nearby': {
        'distance': 800,
        'description': "within half a mile",
    }
}