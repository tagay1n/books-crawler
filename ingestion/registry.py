from . import beznenmiras, commons, darul_kutub, echovek, internet_archive, isxaki, kazanutlary, kfu, kfu_dspace, kfu_repository, kfu_vakyt, magarif, magarif_vakyt, miras, miras_periodicals, nizgar, obuchalka, tatarica, tatargalyame, tataroved, tatkniga, turuz, yazuchy


from . import sarhaan, ftatarstan


SOURCES = {"magarif": magarif, "tatarica": tatarica, "darul_kutub": darul_kutub,
           "sarhaan": sarhaan,
           "ftatarstan": ftatarstan,
           "beznenmiras": beznenmiras,
           "miras_periodicals": miras_periodicals,
           "magarif_vakyt": magarif_vakyt,
           "turuz": turuz,
           "yazuchy": yazuchy,
           "nizgar": nizgar,
           "echovek": echovek,
           "obuchalka": obuchalka,
           "kazanutlary": kazanutlary, "tatkniga": tatkniga, "miras": miras, "commons": commons,
           "isxaki": isxaki, "internet_archive": internet_archive,
           "kfu_repository": kfu_repository,
           "kfu_dspace": kfu_dspace,
           "tataroved": tataroved,
           "kfu_books": kfu.CollectionAdapter("27574"),
           "kfu_manuscripts": kfu.CollectionAdapter("18503"),
           "kfu_il": kfu.CollectionAdapter("28060", tatar_only=True),
           "kfu_azad_halyk": kfu.CollectionAdapter("27528", tatar_only=True),
           "kfu_vakyt": kfu_vakyt,
           "kfu_shura": kfu.CollectionAdapter("25046", tatar_only=True),
           "tatargalyame": tatargalyame}

# Keep the original diagnostic command available after promoting its adapter.
PILOT_SOURCES = {"miras": miras.ARCHIVE_URL}
