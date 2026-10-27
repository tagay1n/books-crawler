from . import darul_kutub, kazanutlary, magarif, tatarica, tatkniga


SOURCES = {"magarif": magarif, "tatarica": tatarica, "darul_kutub": darul_kutub,
           "kazanutlary": kazanutlary, "tatkniga": tatkniga}

# Access experiments are not implemented discovery/download adapters.
PILOT_SOURCES = {"miras": "https://miras.info/projects/mirasxane/books"}
