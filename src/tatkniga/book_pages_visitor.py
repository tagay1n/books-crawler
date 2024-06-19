import json
import csv


from selenium.webdriver.common.by import By

from utils import DOMAIN, BOOKS_METAS, VISITED_BOOK_PAGES
from utils import load_books_pages, load_visited_book_pages, load_books_metas, get_element, create_driver, write_if_new, \
    get_real_path
from utils import mark_visited_book_page


def visit():
    # Load the pages that contain links to the book's pages that we collected during the crawling
    books_pages = load_books_pages()
    # Load the visited book's pages we can skip due to we visited them
    # This is needed to resume after the crash
    visited_books_pages = load_visited_book_pages()
    # Load the metas of the books we collected earlier
    # This is needed to resume after the crash
    book_metas = load_books_metas()
    for l in list(books_pages)[:]:
        _visit_page(l, visited_books_pages, book_metas)


def _visit_page(link, visited_books_pages, book_metas):
    if link in visited_books_pages:
        print("Skipping visited book's page: " + link)
        return
    print("Visiting book page: " + link)

    meta = {"source_link": link}
    driver = create_driver()
    driver.get(link)

    # get price
    element = get_element("//span[@class='sale-price']", driver)
    price = "".join(map(lambda x: x.text.strip() if x else "", element))
    if price:
        meta["price"] = price[:price.index("₽")] if "₽" in price else price

    authors = driver.find_element(By.XPATH, "//div[@class='author-info']/span")
    authors = ", ".join(
        filter(
            lambda x: x and x != "",
            map(lambda x: x.get_attribute("textContent").strip(), authors.find_elements(By.XPATH, "*"))
        )
    )
    title = "".join(map(lambda x: x.get_attribute("textContent").strip(),
                        driver.find_elements(By.XPATH, "//ul[@class='meta-info hidden-md']/li/span")))
    if full_title := _create_full_title(authors, title):
        meta["title"] = full_title

    # get book meta
    element = get_element("//ul[@class='biblio-info']/li", driver)
    for e in element:
        key = e.find_element(By.XPATH, "./label").get_attribute("textContent").lower()
        value = e.find_element(By.XPATH, "./span").get_attribute("textContent")
        if value:
            match key:
                case "обложка":
                    meta["cover"] = value.strip()
                case "формат":
                    meta["format"] = value.strip()
                case "возрастное ограничение":
                    meta["age_limit"] = value.strip()
                case "год издания" if value.strip() != '0':
                    meta["publish_year"] = value.strip()
                case "издательство":
                    meta["publisher"] = value.strip()
                case "язык":
                    meta["language"] = value.strip()
                case "isbn":
                    meta["isbn"] = value.strip()
                case "вес в граммах":
                    meta["weight"] = value.strip()
                case "количество страниц":
                    meta["pages"] = value.strip()

    # get type
    element = get_element("//div[@class='item-type ']", driver)
    if element:
        ty = "".join(map(lambda x: x.get_attribute("textContent").strip(), element))
        if ty == 'Аудио':
            meta["type"] = 'audio'
        elif ty == 'Электронная':
            meta["type"] = 'ebook'
        elif ty == 'Печатная':
            meta["type"] = 'paper'
        elif ty == "":
            meta["type"] = 'book'
        else:
            raise ValueError(f"Unknown type: {ty}")

    # get thumbnail
    if meta.get("type") == "book":
        element = get_element("//img[@class='book-img']", driver)
        if element and (thumbnail := element[0].get_attribute("src")):
            if thumbnail.startswith("/"):
                thumbnail = DOMAIN + thumbnail
            meta["thumbnail"] = thumbnail
        else:
            raise Exception("No thumbnail found for book page: " + link)

    # get direct download link
    if meta.get("type") == "book":
        element = get_element("//a[@class='btn btn-primary btn-sm']", driver)
        for e in element:
            if e.text.strip().lower() == "ЧИТАТЬ PDF".lower():
                meta["download_link"] = e.get_attribute("href")
                break
            elif e.text.strip().lower() == "ЧИТАТЬ В СТАРОМ ФОРМАТЕ".lower():
                meta["//tatkniga.ru/books/35837'"] = e.get_attribute("href")
                break
        else:
            print("No download link found for book page: " + link)
            driver.quit()
            return
    if meta.get("type") == "audio":
        element = get_element("//a[@class='btn btn-green btn-sm']", driver)
        if not element or len(element) != 1:
            print("Incorrect count of links found for audio page: " + link)
            driver.quit()
            return
        for e in element:
            if e.text.strip().lower() == "Скачать".lower():
                meta["download_link"] = e.get_attribute("href")
                break
        else:
            print("No download link found for audio page: " + link)
            driver.quit()
            return

    # get description
    element = get_element("//div[@class='item-excerpt trunc']", driver)
    if element and (desc := "".join(map(lambda x: x.text.strip(), element))):
        meta["description"] = desc

    driver.quit()
    if meta not in book_metas:
        if 'Бесплатно' in meta["price"]:
            book_metas.append(meta)
            with open(BOOKS_METAS, "w") as f:
                json.dump(book_metas, f, indent=4, ensure_ascii=False)
                f.flush()
        elif meta["price"]:
            if meta["type"] == "ebook":
                if "атарский" in meta["language"]:
                    meta['description'] = meta.get('description', "").replace("\n", "")
                    print(f"Tatar ebook found: {meta}")
                    with open("paid_files.csv", "a+", newline="") as f:
                        w = csv.DictWriter(f, meta.keys())
                        w.writerow(meta)

    mark_visited_book_page(link)


def _create_full_title(author, title):
    if title.startswith(author):
        return title
    full_title = []
    if author:
        full_title.append(author)
    if title:
        full_title.append(title)
    return " - ".join(full_title)
