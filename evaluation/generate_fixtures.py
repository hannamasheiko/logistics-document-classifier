from pathlib import Path
from textwrap import wrap

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


OUTPUT_DIRECTORY = Path(__file__).resolve().parent / "documents"

FIXTURES = {
    "tuning-bol-blank-delivery.pdf": (
        "BILL OF LADING",
        "BOL No: NB-20418",
        "Shipper: North Bay Components, Reno, NV",
        "Consignee: Harbor Machine Works, Sacramento, CA",
        "Carrier: Northstar Freight LLC",
        "Origin: Reno, NV  Destination: Sacramento, CA",
        "Cargo: 12 pallets of machine parts  Gross weight: 8,400 lb",
        "Received by Northstar Freight LLC for transport and delivery to the consignee.",
        "Freight terms: prepaid",
        "Delivery date: ____________________",
        "Receiver signature: _______________",
    ),
    "tuning-pod-bol-reference.pdf": (
        "PROOF OF DELIVERY",
        "Waybill: WB-77102  BOL reference: NB-20418",
        "Carrier: Swift Harbor Transport",
        "Destination: Sacramento, CA",
        "Status: DELIVERED",
        "Delivered on: 2026-08-18 at 14:32",
        "Received by: Elena Ortiz",
        "Recipient acknowledgement: Elena Ortiz / signed electronically",
        "Packages delivered: 12",
    ),
    "tuning-invoice-with-bol-reference.pdf": (
        "FREIGHT BROKER INVOICE",
        "Invoice: FBI-4029",
        "Provider: Blue Route Logistics LLC",
        "Bill to: North Bay Components",
        "Load: LD-2901  BOL reference: NB-20418",
        "Reno, NV to Sacramento, CA",
        "Linehaul service: $1,450.00",
        "Fuel surcharge: $210.00",
        "Detention: $75.00",
        "Amount due: $1,735.00",
        "Payment terms: Net 30",
    ),
    "tuning-commercial-invoice-with-freight.pdf": (
        "COMMERCIAL INVOICE",
        "Exporter: Atlas Tools Ltd.  Importer: West Ridge Supply",
        "Product: steel cutting tools  Quantity: 240 units",
        "HS code: 8207.70  Country of origin: Germany",
        "Goods value: USD 18,600.00",
        "Freight value for customs: USD 900.00",
        "Incoterm: CIP Seattle",
        "Total customs value: USD 19,500.00",
        "Purpose: sale of merchandise for import",
    ),
    "tuning-combined-bol-pod.pdf": (
        "STRAIGHT BILL OF LADING AND DELIVERY RECEIPT",
        "Document: CMB-9104",
        "Shipper: Alpine Paper Co.  Consignee: Metro Print House",
        "Carrier: Canyon Freight Inc.",
        "Cargo: 18 rolls of paper  Weight: 12,200 lb",
        "Canyon Freight received the goods for carriage from Denver to Boulder.",
        "Final delivery status: DELIVERED",
        "Delivered at Boulder, CO on 2026-08-21 at 09:10",
        "Received and signed by: Marcus Lee",
    ),
    "tuning-incomplete-bol-fragment.pdf": (
        "BILL OF LADING",
        "Document fragment: BOL-88017",
        "Carrier: text unreadable",
        "Shipper: [cropped]",
        "Remaining shipment, consignee, cargo, and transport terms are unavailable.",
    ),
    "tuning-incomplete-invoice-fragment.pdf": (
        "LOGISTICS INVOICE",
        "Invoice fragment: LI-7720",
        "Provider: Westline Logistics",
        "Bill to: [cropped]",
        "Charge lines, amount due, and payment terms are unavailable.",
    ),
    "tuning-incomplete-customs-fragment.pdf": (
        "CUSTOMS DECLARATION",
        "Declaration fragment: CD-5108",
        "Exporter: [unreadable]",
        "Product, quantity, value, origin, and customs-purpose sections are unavailable.",
    ),
    "heldout-bol-produce.pdf": (
        "UNIFORM STRAIGHT BILL OF LADING",
        "Shipment ID: USL-12008",
        "Shipper: Valley Produce Cooperative, Fresno, CA",
        "Consignee: North Market Foods, Portland, OR",
        "Motor carrier: Redwood Haulage",
        "Redwood Haulage acknowledges receipt of the goods for transportation to consignee.",
        "Contents: 22 refrigerated pallets of fresh produce",
        "Gross weight: 31,700 lb  Temperature: 36 F",
        "Origin: Fresno, CA  Destination: Portland, OR",
    ),
    "heldout-bol-ocean.pdf": (
        "OCEAN BILL OF LADING",
        "B/L Number: OBL-66201",
        "Shipper: Pacific Ceramics Export",
        "Consignee: Coastal Home Imports",
        "Ocean carrier: Meridian Vessel Lines",
        "Port of loading: Long Beach  Port of discharge: Oakland",
        "Goods received for carriage: 2 containers ceramic tile",
        "Container IDs: MCU10021 and MCU10022  Total weight: 39,000 kg",
    ),
    "heldout-pod-electronics.pdf": (
        "DELIVERY CONFIRMATION",
        "Tracking number: DC-441991",
        "Final status: Delivered",
        "Delivered to: Austin, TX receiving dock",
        "Delivery time: 2026-08-26 11:47 CDT",
        "Recipient: Priya Shah",
        "Signature captured: P. Shah",
        "Items delivered: 4 sealed electronics cartons",
    ),
    "heldout-pod-furniture.pdf": (
        "SIGNED DELIVERY RECEIPT",
        "Receipt: SDR-5077",
        "Carrier: Hearthside Home Delivery",
        "Order delivered at Madison, WI on August 27, 2026 at 16:05",
        "Delivery completed: two furniture crates received without visible damage.",
        "Accepted by customer: Jonah Reed",
        "Customer signature: Jonah Reed",
    ),
    "heldout-invoice-carrier.pdf": (
        "CARRIER FREIGHT INVOICE",
        "Invoice number: CFI-38155",
        "Carrier: Granite State Transport",
        "Bill to: North Market Foods",
        "Shipment lane: Portland, OR to Boise, ID",
        "Transportation linehaul: $2,080.00",
        "Reefer fuel surcharge: $285.00",
        "Stop-off service: $95.00",
        "Balance due: $2,460.00  Due date: 2026-09-30",
    ),
    "heldout-invoice-drayage.pdf": (
        "LOGISTICS SERVICES INVOICE",
        "Invoice LS-9082 from Seaport Drayage Partners",
        "Bill to: Coastal Home Imports",
        "Container drayage service: $780.00",
        "Chassis rental: $160.00",
        "Port congestion fee: $125.00",
        "Detention: $90.00",
        "Total amount due: $1,155.00",
        "Terms: payable within 15 days",
    ),
    "heldout-other-packing-list.pdf": (
        "EXPORT PACKING LIST",
        "Seller: Summit Outdoor Equipment",
        "Buyer: Nordic Trail Retail AB",
        "Packing list number: PL-20071",
        "Carton 1-8: camping stoves, 160 units",
        "Carton 9-12: cookware sets, 80 units",
        "Net goods weight: 1,120 kg  Gross goods weight: 1,260 kg",
        "Purpose: identify merchandise packed for export; no amount is due.",
    ),
    "heldout-other-purchase-order.pdf": (
        "PURCHASE ORDER",
        "PO number: PO-77830",
        "Buyer: Metro Print House",
        "Supplier: Alpine Paper Co.",
        "Order: 30 rolls coated paper at $410.00 each",
        "Merchandise total: $12,300.00",
        "Requested delivery date: 2026-09-12",
        "Purpose: buyer authorization to supply the listed goods.",
    ),
    "heldout-combined-bol-pod.pdf": (
        "BILL OF LADING / COMPLETED DELIVERY RECORD",
        "Combined document: CR-30119",
        "Shipper: Greenline Packaging  Consignee: Lakeside Distribution",
        "Carrier: Interstate Cargo LLC",
        "Interstate Cargo received 16 pallets for carriage from Chicago to Milwaukee.",
        "Cargo weight: 10,600 lb",
        "Delivery status: DELIVERED IN FULL",
        "Delivered in Milwaukee on 2026-08-29 at 08:44",
        "Consignee acknowledgement and signature: Dana Brooks",
    ),
    "heldout-incomplete-pod-fragment.pdf": (
        "PROOF OF DELIVERY",
        "Fragment reference: POD-1140",
        "Tracking: TR-50122",
        "Delivery status: [unreadable]",
        "Date and time: [cropped]",
        "Recipient section is missing from the available page content.",
    ),
    "v2-heldout-bol-rail.pdf": (
        "RAIL BILL OF LADING",
        "Rail B/L: RBL-20773",
        "Shipper: Prairie Grain Cooperative, Omaha, NE",
        "Consignee: Riverbend Milling, St. Louis, MO",
        "Rail carrier: Central Plains Railway",
        "Central Plains Railway received the goods for rail transportation to consignee.",
        "Cargo: 3 covered hopper cars of milling wheat",
        "Origin: Omaha, NE  Destination: St. Louis, MO",
        "Total shipment weight: 284,000 lb",
    ),
    "v2-heldout-bol-intermodal.pdf": (
        "NEGOTIABLE INTERMODAL BILL OF LADING",
        "B/L number: IMB-44920",
        "Shipper: Cascade Outdoor Goods",
        "Consignee: Atlantic Sports Distribution",
        "Contracting carrier: Summit Intermodal Transport",
        "Goods accepted for carriage from Tacoma, WA to Newark, NJ.",
        "Cargo: 2 sealed containers of sporting equipment",
        "Container numbers: SIMU88210 and SIMU88211",
        "Freight terms: collect",
    ),
    "v2-heldout-pod-certificate.pdf": (
        "DELIVERY COMPLETION CERTIFICATE",
        "Certificate: DCC-6109",
        "Carrier: Keystone Regional Freight",
        "Shipment delivered in full at Harrisburg, PA",
        "Completed delivery: September 4, 2026 at 10:18 EDT",
        "Packages received: 9 industrial pump crates",
        "Receiving representative: Amina Clarke",
        "Electronic acknowledgement: A. Clarke",
    ),
    "v2-heldout-pod-freight-receipt.pdf": (
        "SIGNED FREIGHT RECEIPT",
        "Receipt number: SFR-88341",
        "Carrier: Desert Line Transport",
        "Final status: DELIVERED",
        "Delivery location: Phoenix, AZ distribution center",
        "Delivered on September 5, 2026 at 15:42 MST",
        "All 14 cartons received without exception.",
        "Signed for by: Lucas Nguyen",
    ),
    "v2-heldout-invoice-forwarder.pdf": (
        "FREIGHT FORWARDER INVOICE",
        "Invoice: FFI-19024",
        "Provider: Continental Forwarding Group",
        "Bill to: Cascade Outdoor Goods",
        "International freight forwarding: $1,920.00",
        "Origin handling: $185.00",
        "Documentation service: $75.00",
        "Amount due: $2,180.00",
        "Payment terms: Net 21",
    ),
    "v2-heldout-invoice-warehouse.pdf": (
        "WAREHOUSING AND LOGISTICS SERVICES INVOICE",
        "Invoice number: WLS-33018",
        "Service provider: Harbor Fulfillment LLC",
        "Bill to: Atlantic Sports Distribution",
        "Inbound pallet handling: $420.00",
        "Thirty-day storage service: $680.00",
        "Outbound order preparation: $235.00",
        "Total balance due: $1,335.00  Due: October 1, 2026",
    ),
    "v2-heldout-other-inspection-certificate.pdf": (
        "QUALITY INSPECTION CERTIFICATE",
        "Certificate: QIC-7718",
        "Manufacturer: Meridian Fastener Works",
        "Product batch: stainless steel bolts B-9021",
        "Sample size: 120 units",
        "Measurements verified: diameter, thread pitch, and tensile strength",
        "Inspection result: batch conforms to specification MFW-88.",
        "Purpose: certify product quality before release from manufacturing.",
    ),
    "v2-heldout-other-pick-list.pdf": (
        "WAREHOUSE PICK LIST",
        "Pick batch: WPL-52041",
        "Facility: North Hub Fulfillment Center",
        "Order wave: 2026-09-06-AM",
        "Bin A-14: safety gloves, 36 units",
        "Bin C-08: protective goggles, 24 units",
        "Bin D-22: high-visibility vests, 18 units",
        "Purpose: direct internal warehouse picking and order assembly.",
    ),
    "v2-heldout-combined-intermodal-delivery.pdf": (
        "INTERMODAL BILL OF LADING AND FINAL DELIVERY ACKNOWLEDGEMENT",
        "Combined record: IFD-72011",
        "Shipper: Summit Appliance Parts  Consignee: Lakeshore Repair Supply",
        "Carrier: Crossland Intermodal LLC",
        "Crossland accepted 11 pallets for carriage from Columbus to Detroit.",
        "Shipment weight: 7,850 lb",
        "Final delivery: DELIVERED in Detroit on September 7, 2026 at 13:25",
        "Consignee acknowledgement and signature: Renee Carter",
    ),
    "v2-heldout-incomplete-invoice-fragment.pdf": (
        "FREIGHT SERVICES INVOICE",
        "Fragment: FSI-11804",
        "Provider: [partially unreadable]",
        "Bill to: Great Lakes Components",
        "Service lines, balance due, and payment terms are missing from this fragment.",
    ),
    "g3-extraction-contradiction-bol.pdf": (
        "BILL OF LADING",
        "BOL No: BOL-40217",
        "Shipper: Meridian Freight Solutions, Dallas, TX",
        "Consignee: Meridian Freight Solutions, Dallas, TX",
        "Carrier: Lone Star Trucking",
        "Meridian Freight Solutions received the goods for transport to the consignee.",
        "Cargo: 8 pallets of packaging materials  Gross weight: 6,200 lb",
        "Origin: Dallas, TX  Destination: Dallas, TX",
    ),
}


def write_fixture(path: Path, lines: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(
        str(path),
        pagesize=letter,
        invariant=1,
        pageCompression=0,
    )
    pdf.setTitle(path.stem)
    pdf.setAuthor("Synthetic evaluation fixture")
    text = pdf.beginText(54, 738)
    text.setFont("Helvetica", 10)
    for line in lines:
        for wrapped_line in wrap(line, width=88) or [""]:
            text.textLine(wrapped_line)
        text.textLine("")
    pdf.drawText(text)
    pdf.showPage()
    pdf.save()


def main() -> None:
    for filename, lines in FIXTURES.items():
        write_fixture(OUTPUT_DIRECTORY / filename, lines)
    print(f"Generated {len(FIXTURES)} deterministic PDF fixtures in {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()
