
from src.contracts.models import ContractRecord
from src.scraper import paginate_contract_links
from src.scraper.detail import process_contract_detail
import time


SEARCH_URL = (
    "https://contratos-publicos.comunidad.madrid/contratos"
)
def main():
    urls = paginate_contract_links(SEARCH_URL, max_pages=15)
    selected = urls[:100]

    records: list[ContractRecord] = []

    for idx, url in enumerate(selected, 1):
        print(f"[{idx}/{len(selected)}] {url}")
        record = process_contract_detail(url)
        records.append(record)
        time.sleep(1)

    print("Processed:", len(records))


if __name__ == "__main__":
    main()
