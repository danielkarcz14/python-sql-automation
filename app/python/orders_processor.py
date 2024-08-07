import csv
import requests
import os
import logging

from io import StringIO
from db_connection import db_connection
from event_logger import EventLogger 
from datetime import timedelta, date, time, datetime

conn, cur, user = db_connection()
event_logger = EventLogger(conn, cur)

# Limit pro opakování pokusu připojení k db
RETRY_LIMIT = 5

class OrdersProcessor:
    def __init__(self, event_logger):
        self.event_logger = event_logger

    def fetch_orders(self, url):
        # Stažení objednávek z posktytnutého URL feedu ve formátu CSV
        response = requests.get(url)
        if response.status_code == 200:
            content = StringIO(response.text)
            return csv.DictReader(content)
        else:
            error_message = f"Chyba při stazeni objednavek z URL: {url}"
            self.event_logger.log_error("OrderProcessor", "fetch_orders", error_message)
            return None

    def extract_date(self, date_time_str):
        return date_time_str.split()[0]

    def filter_orders(self, orders, target_date):
        # Filtrování objednávek se včerejším datem 
        return [order for order in orders if self.extract_date(order['date']) == target_date.strftime("%Y-%m-%d")]

    def process_orders(self, url, target_date):
        orders = self.fetch_orders(url)
        filtered_orders = self.filter_orders(orders, target_date)
        for order in filtered_orders:
            if order['orderItemCode'].startswith('H1') or order['orderItemCode'].startswith('H2'):
                price = order['orderItemUnitPriceWithVat'].replace(",", ".")

                # Zkontrolovat, zda objednávka s tímto id již existuje, pokud ne, vložit
                if self.check_order_exists(order['id']) is None:
                    try:
                        cur.execute("INSERT INTO objednavky (id_objednavky, datum_vytvoreni) VALUES (?, ?)", (order['id'], order['date']))
                        conn.commit()  # Commit po každé nové objednávce
                        event_logger.log_success(user, os.path.basename(__file__), f"vlozena objednavka s id: {order['id']}")
                    except Exception as e:
                        event_logger.log_error(user, os.path.basename(__file__), f"chyba pri vlozeni objednavky s id {order['id']}, chyba: {str(e)}")
                # Uložit id vložené objednávky do proměnné
                cur.execute("SELECT id_objednavky FROM objednavky WHERE id_objednavky = ?", (order['id'],))
                order_id = cur.fetchone()[0]

                # Vkládání položek dané objednávky do tabulky polozky_objednavky
                if order['id'] == order_id and self.check_order_item_exists(order_id, order['orderItemCode'])[0] == 0:
                    try:
                        cur.execute(
                            """
                            INSERT INTO polozky_objednavky (id_objednavky, mnozstvi_ks, id_produktu, cena, nazev) VALUES (?, ?, ?, ?, ?)
                            """, (order_id, order['orderItemAmount'], order['orderItemCode'], price, order['orderItemVariantName']))
                        conn.commit()  # Commit hned po každé vložené položce objednávky
                        event_logger.log_success(user, os.path.basename(__file__), f"vlozena polozka objednavky s id: {order['orderItemCode']} {order['orderItemAmount']}ks")
                    except Exception as e:
                        event_logger.log_error(user, os.path.basename(__file__), f"chyba pri vlozeni polozky objednavky s id polozky {order['orderItemCode']}, chyba: {str(e)}")

    def check_order_exists(self, order_id):
        cur.execute("SELECT id_objednavky FROM objednavky WHERE id_objednavky = ?", (order_id,))
        return cur.fetchone()

    def check_order_item_exists(self, order_id, product_code):
        cur.execute("SELECT COUNT(*) FROM polozky_objednavky WHERE id_objednavky = ? AND id_produktu = ?", (order_id, product_code))
        return cur.fetchone()


def main():
    logging.basicConfig(filename="logfile.log", level=logging.INFO)
    logging.info(f'Order processing job started at {datetime.now()}')
    # URL adresa pro stahování objenávek ze Shoptetu v CSV formátu
    url = ""
    yesterday = date.today() - timedelta(days=1)

    
    # V případě selhání připojení k databázi opakovat max RETRY_LIMIT
    retry_count = 0
    while retry_count < RETRY_LIMIT:
        try:
            order_processor = OrdersProcessor(event_logger)
            order_processor.process_orders(url, yesterday)
            break
        except Exception as e:
            if conn:
                conn.close()
            retry_count += 1
            time.sleep(5)

    # Ukončit spojení s db
    if conn:
        conn.close()
    logging.info(f'Order processing job finished at {datetime.now()}')

if __name__ == "__main__":
    main()
