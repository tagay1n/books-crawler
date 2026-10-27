from . import darul_kutub, kazanutlary, magarif, miras, tatarica, tatkniga


SOURCES = {"magarif": magarif, "tatarica": tatarica, "darul_kutub": darul_kutub,
           "kazanutlary": kazanutlary, "tatkniga": tatkniga, "miras": miras}

# Keep the original diagnostic command available after promoting its adapter.
PILOT_SOURCES = {"miras": miras.ARCHIVE_URL}
