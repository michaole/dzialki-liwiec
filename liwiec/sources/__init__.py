from liwiec.sources import adresowo, gratka, olx, otodom

# Portal name → scrape(progress_callback) -> DataFrame
SCRAPERS = {
    otodom.NAME: otodom.scrape,
    olx.NAME: olx.scrape,
    gratka.NAME: gratka.scrape,
    adresowo.NAME: adresowo.scrape,
}
