import os
import matplotlib.pyplot as plt
import smtplib

from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from pathlib import Path
from fpdf import FPDF
from datetime import timedelta, datetime, date
from db_connection import db_connection
from event_logger import EventLogger

conn, cur, user = db_connection()
event_logger = EventLogger(conn, cur)



# Cesta pro ukladani reportu
current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
output_dir = current_dir / "reporty"

# Vytvoreni slozky pokud neexistuje
output_dir.mkdir(parents=True, exist_ok=True)

# Parametry pro procedury
today_date = datetime.now().date()
end_date = today_date - timedelta(days=30)

END_DATE_STR = today_date.strftime('%Y%m%d')
START_DATE_STR = end_date.strftime('%Y%m%d')

KG = "kg"
KS = "ks"
ALL = ''


def main():
    report_mnozstvi_surovin(KG, "1.mnozstvi_krusiva.png")
    report_spotreba_surovin(KG, "2.spotreba_krusiva.png")
    report_mnozstvi_surovin(KS, "3.mnozstvi_kbeliku.png")
    report_spotreba_surovin(KS, "4.spotreba_kbeliku.png")

    create_pdf_report()
    send_report()

    conn.close()


def generate_graph(y_data, x_data, y_label, x_label, title, suffix):
    # Vytvoření gradientu barev
    min_value = 0
    max_value = max(x_data)
    colors = [plt.cm.YlOrRd_r((value - min_value) / (max_value - min_value)) for value in x_data]

    # Vytvoření horizontálního sloupcového grafu
    plt.figure(figsize=(12, 10))  # Zvětšení rozměrů obrázku
    bars = plt.barh(y_data, x_data, color=colors)  # Použití barev ze vytvořeného gradientu
    plt.xlabel(y_label, fontsize=16)
    plt.ylabel(x_label, fontsize=16)
    plt.title(title, fontsize=20, fontweight='bold')

    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)

    # Přidání popisků hodnot na konci každého baru
    for bar, value in zip(bars, x_data):
        plt.text(bar.get_width() + 10, bar.get_y() + bar.get_height() / 2, f'{value} {suffix}', va='center')

    plt.tight_layout()


def fetch_query(query, *args):
    try:
        cur.execute(query, *args)
        return cur.fetchall()
    except Exception as e:
        print(f"Error executing query: {e}")


def query_mnozstvi_suroviny(merna_jednotka):
    # Mnozstvi krusiva dotaz
    if merna_jednotka == '':
        query = '''
        SELECT id_suroviny, nazev, zrnitost, mnozstvi, merna_jednotka 
        FROM sklad_surovin
        ORDER BY mnozstvi DESC
        '''
        data = fetch_query(query)
    else:
        query = '''
        SELECT id_suroviny, nazev, zrnitost, mnozstvi, merna_jednotka 
        FROM sklad_surovin
        WHERE merna_jednotka = ?
        ORDER BY mnozstvi DESC
        '''
        data = fetch_query(query, merna_jednotka)

    json_data = []
    for row in data:
        formatted_row = {
            "id_suroviny": row[0],
            "nazev": row[1],
            "zrnitost": row[2],
            "mnozstvi_na_sklade": float(row[3]),
            "merna_jednotka" : row[4]
        }
        json_data.append(formatted_row)
    return data, json_data


def query_spotreba_suroviny(merna_jednotka):
    if merna_jednotka == "kg":
        query = '''
        spotrebova_surovin @p_start_date = ?, @p_end_date = ?, @p_merna_jednotka = ?;
        '''
    elif merna_jednotka == "ks":
        query = '''
        spotrebova_surovin @p_start_date = ?, @p_end_date = ?, @p_merna_jednotka = ?;
        '''
    elif merna_jednotka == "":
        query = '''
        spotrebova_surovin @p_start_date = ?, @p_end_date = ?, @p_merna_jednotka = ?;
        '''
    
    data = fetch_query(query, (START_DATE_STR, END_DATE_STR, merna_jednotka))
    json_data = []
    for row in data:
        formatted_row = {
            "id_suroviny": row[0],
            "nazev": row[1],
            "zrnitost": row[2],
            "spotreba_za_mesic": float(row[3]), 
        }
        json_data.append(formatted_row)
    return data, json_data


def report_mnozstvi_surovin(merna_jednotka, filename):
    data, _ = query_mnozstvi_suroviny(merna_jednotka)
    id = [row[0] for row in data]
    mnozstvi = [float(row[3]) for row in data]
    surovina_name = "krušiva" if merna_jednotka == "kg" else "kbelíků"
    generate_graph(id, mnozstvi, f"Množství {surovina_name} v {merna_jednotka}", "ID suroviny", f"Aktuální množství {surovina_name} na skladě v {merna_jednotka}", merna_jednotka)
    plt.savefig(output_dir / filename)
    

def report_spotreba_surovin(merna_jednotka, filename):
    data, _ = query_spotreba_suroviny(merna_jednotka)
    id = [row[0] for row in data]
    mnozstvi = [float(row[3]) for row in data]
    surovina_name = "krušiva" if merna_jednotka == "kg" else "kbelíků"
    generate_graph(id, mnozstvi,  f"Spotřebované množství {surovina_name} v {merna_jednotka}", "ID suroviny", f"Spotřeba {surovina_name} v {merna_jednotka} / 30 dní", merna_jednotka)
    plt.savefig(output_dir / filename)


def calculate_days_left(mnozstvi, spotreba):
    if spotreba == 0:
        return float('inf')   
    return round(mnozstvi / spotreba)


def generate_recommendation():
    _, data_spotreba = query_spotreba_suroviny(ALL)
    _, data_mnozstvi = query_mnozstvi_suroviny(ALL)

    spotreba_dict = {item['id_suroviny']: item['spotreba_za_mesic'] for item in data_spotreba}

    recommendations = []
    format_words = ['den', 'dny', 'dní']
    
    for mnozstvi_data in data_mnozstvi:
        mnozstvi = mnozstvi_data['mnozstvi_na_sklade']

        if mnozstvi_data['id_suroviny'] in spotreba_dict.keys():
            spotreba = spotreba_dict[mnozstvi_data['id_suroviny']]
            days_left = calculate_days_left(mnozstvi, spotreba)
          
        if days_left < 10:
            word_index = 0 if days_left == 1 else (1 if days_left < 5 else 2)
            recommendations.append(f"Dokoupit {mnozstvi_data['nazev'].strip()}[{mnozstvi_data['id_suroviny']}], surovina dojde priblizne za {days_left} {format_words[word_index]}.")
    return recommendations


def create_pdf_report():
        # Define the font color as RGB values (dark gray) 
    font_color = (64, 64, 64)

    # Find all PNG files in the output folder
    chart_filenames = [str(chart_path) for chart_path in output_dir.glob("*.png")]
     # Create a PDF document and set the page size
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 24)

    # Add the overall page title
    title = f"Report skladu ze dne {date.today().strftime('%d.%m.%Y')}"
    pdf.set_text_color(*font_color)
    pdf.cell(0, 20, title, align='C', ln=1)

    # Add each chart to the PDF document
    for chart_filename in chart_filenames:
        pdf.ln(10)  # Add padding at the top of the next chart
        pdf.image(chart_filename, x=None, y=None, w=pdf.w - 20, h=0)

    pdf.add_page()
    # Nadpis
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, "Doporuceni k nakupu", ln=True)
    recommendations = generate_recommendation()
    pdf.set_font('Arial', 'B', 8)
    pdf.set_text_color(0,0,0)
    for recommendation in recommendations:
        r = str(recommendation).encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 5, txt=r)
    # Save the PDF document to a file on disk
    pdf.output(output_dir / "report_skladu.pdf", "F")


def send_report():
    try:
        sender = 'danielkarcz14@gmail.com'
        receiver = 'danielkarcz14@gmail.com'
        subject = 'Report skladových zásob'
    
        message = MIMEMultipart()
        message['From'] = sender
        message['To'] = receiver
        message['Subject'] = subject

        # Read PDF file

        filename = f"report_skladu_{today_date.strftime('%d_%m_%Y')}.pdf"

        pdf_file_path = output_dir / "report_skladu.pdf"
        with open(pdf_file_path, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())

        # Encode PDF file
        encoders.encode_base64(part)

        # Add attachment
        part.add_header('Content-Disposition', f'attachment; filename= {filename}')
        message.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, "rtmw xbtg fqqb nzoy")
        server.sendmail(sender, receiver, message.as_string())
        server.quit()

        event_logger.log_success(user, os.path.basename(__file__), f"Odeslan email o stavu skladu")
    except smtplib.SMTPException as e:
        event_logger.log_error(user, os.path.basename(__file__), f"chyba pri odesilani emailu o stavu skladu, chyba: {str(e)}")


    
if __name__ == "__main__":
    main()
