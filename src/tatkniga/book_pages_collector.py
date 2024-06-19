from selenium.common.exceptions import StaleElementReferenceException

from utils import load_visited_pages, load_books_pages, get_element, create_driver, get_hostname, write_if_new


def collect(books_pages_sink, visited_pages_sink, entry_point, books_page_mask, skip_filters):
    """
    This function collects the links to the book's pages and stores them in the file.

    :param books_pages_sink: file to store the links to the book's pages
    :param visited_pages_sink: file to store the visited pages
    :param entry_point: the page to start crawling
    :param books_page_mask: the mask for the pages that we are interested in
    :param skip_filters: the mask for the pages that we are not interested in
    :return:
    """
    hostname_filter = get_hostname(entry_point)

    # Load the visited pages we can skip at the time of crawling and add new ones during the crawling
    # This is needed to resume crawling after the crash
    vps = load_visited_pages()
    # Load the pages that contain links to the book's pages that we already visited and add new ones during the crawling
    # This is needed to resume crawling after the crash
    bps = load_books_pages()

    def crawl(link_to_visit, visited_links, book_pages):
        """
        This function visits the link, collects the links to the book's pages and stores them in the file.

        :param link_to_visit: link to visit
        :param visited_links: accumulator of the visited links
        :param book_pages: accumulator of the links to the book's pages
        :return:
        """
        write_if_new(link_to_visit, visited_links, visited_pages_sink)
        print(f"Visiting link: {link_to_visit}")
        driver = create_driver()
        driver.get(link_to_visit)

        if not (elements := get_element("//a[@href]", driver)):
            print("No links found on the page " + link_to_visit)
            driver.quit()
            return

        found_links = set()
        for element in elements:
            try:
                link = element.get_attribute("href")
            except StaleElementReferenceException:
                continue

            if not link:
                print("Element does not have href attribute")
                continue

            if link.endswith(".xlsx"):
                print(f"Found xlsx file, skipping it: {link}")
                continue

            if link.startswith("/"):
                link = hostname_filter + link
                print(f"Fixed link: {link}")

            if any(link.startswith(skip) for skip in skip_filters):
                print(f"Skipping link: {link} due to it is in the skip list")
                continue

            # Check if link matches pattern of books page's link and if it does, then add it to the list of the books
            # pages
            if link.startswith(books_page_mask):
                write_if_new(link, book_pages, books_pages_sink)
                print(f"Found books page: {link}")

            # Here we know the link is not the book's page, but it can be the page that contains the link to the book's
            # page. Check if link is not in the list of the visited pages and if it does, then add it to the list of the
            # pages to visit
            elif link.startswith(hostname_filter) and link not in visited_links and not link.endswith("/our-stores"):
                print(f"Found link to visit: {link}")
                found_links.add(link)

        driver.quit()
        # Visit the found links on the page
        for link in found_links:
            if link not in visited_links:
                crawl(link, visited_links, book_pages)

    crawl(entry_point, vps, bps)
