from app.medication_foundation_v18_routes import infer_concentration_mg_per_ml, parse_vmd_xml

fixture = b"""<?xml version='1.0' encoding='UTF-8'?>
<ProductInformation>
  <Product>
    <ProductName>UAT Veterinary Product 10 mg/ml solution for injection</ProductName>
    <VMNumber>Vm-SYNTHETIC-PARSER-001</VMNumber>
    <Territory>GB</Territory>
    <MarketingAuthorisationHolder>UAT Holder</MarketingAuthorisationHolder>
    <DistributionCategory>POM-V</DistributionCategory>
    <PharmaceuticalForm>Solution for injection</PharmaceuticalForm>
    <ActiveSubstance>UAT Active Substance</ActiveSubstance>
    <TargetSpecies>Dog</TargetSpecies>
    <RouteOfAdministration>IV</RouteOfAdministration>
    <AuthorisationStatus>current</AuthorisationStatus>
    <LastUpdated>2026-07-27T00:00:00+00:00</LastUpdated>
  </Product>
</ProductInformation>
"""

fingerprint, products = parse_vmd_xml(fixture, "https://example.invalid/vmd-fixture.xml")
assert len(fingerprint) == 64
assert len(products) == 1
product = products[0]
assert product.source_product_id == "Vm-SYNTHETIC-PARSER-001"
assert product.product_name.startswith("UAT Veterinary Product")
assert product.target_species == ["Dog"]
assert product.routes == ["IV"]
assert product.active_substances == ["UAT Active Substance"]
assert product.concentration_mg_per_ml == 10.0
assert infer_concentration_mg_per_ml("UAT 250 micrograms/ml") == 0.25
assert infer_concentration_mg_per_ml("UAT 2 g/ml") == 2000.0
print("MEDICATION_V18_VMD_PARSER_TEST_PASSED")
