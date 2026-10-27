from . import darul_kutub, kazanutlary, magarif, tatarica


SOURCES = {"magarif": magarif, "tatarica": tatarica, "darul_kutub": darul_kutub,
           "kazanutlary": kazanutlary}

# Access experiments are not implemented discovery/download adapters.
PILOT_SOURCES = {"miras": "https://miras.info/projects/mirasxane/books"}
