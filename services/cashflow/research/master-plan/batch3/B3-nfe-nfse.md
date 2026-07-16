# B3 — NFe + NFS-e Integration Master Plan

> L2 Cashflow · Batch 3 Compliance & Integrations
> Generated 2026-07-10 · References: B1-compliance-order, B1-risks-blockers, REPORT-TECHNICAL §4

---

## 0. Scope & Dependencies

| Aspect | Detail |
|--------|--------|
| **Scope** | NFe (goods) + NFS-e (services) integration with SEFAZ and municipal tax authorities |
| **Depends on** | Tax Engine (Batch 1/2), CNPJ Validation (Batch 1), Digital Certificates (Batch 2) |
| **Risk** | HIGH — SOAP complexity, 5,570+ municipal variations, SEFAZ downtime, XML signing security |
| **Target** | Phase 1 (MVP): NFS-e SP only + NFe SVRS single autorizador. Phase 2: All autorizadores + top 100 municipalities |

**Prior decisions**:
- D-COMP-002: NFS-e (services) before NFe (products) — L2's market is services-first
- D-COMP-003: São Paulo first for NFS-e — largest market, best-documented ABRASF 2.03

---

## 1. NFe Architecture — SEFAZ Client

### 1.1 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    L2 Cashflow Platform                      │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │ Invoice  │──→│ NFe Renderer │──→│  NFe XML Generator  │  │
│  │ Module   │   │              │   │  (XSD-validated)    │  │
│  └──────────┘   └──────────────┘   └────────┬────────────┘  │
│                                              │               │
│  ┌──────────────┐   ┌───────────────────────┘               │
│  │ Certificate  │──→│  XML Signer (XMLDSig SHA-256)         │
│  │ Manager      │   │  + Chave de Acesso (44-digit)         │
│  └──────────────┘   └────────┬──────────────────────────────┘
│                              │                               │
│  ┌──────────────┐   ┌───────▼──────────┐                   │
│  │ Autorizador  │──→│  SEFAZ SOAP 1.2  │──→ SEFAZ          │
│  │ Router       │   │  Client (mTLS)   │    Autorizadores   │
│  └──────────────┘   └───────┬──────────┘                   │
│                              │                               │
│  ┌──────────────┐   ┌───────▼──────────┐                   │
│  │ Status       │←──│  Callback /      │                   │
│  │ Poller       │   │  Polling Engine  │                   │
│  └──────────────┘   └──────────────────┘                   │
│                              │                               │
│  ┌──────────────┐   ┌───────▼──────────┐                   │
│  │ NFe Store    │←──│  Event Bus       │                   │
│  │ (DB)         │   │  nfe.authorized  │                   │
│  └──────────────┘   │  nfe.cancelled   │                   │
│                     │  nfe.rejected    │                   │
│                     └──────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Autorizador Routing

Each emitter (CNPJ) maps to a specific SEFAZ autorizador based on state:

| Autorizador | States | Code |
|-------------|--------|------|
| SVAN | Nacional (default) | SVAN |
| SVRS | Sul/Sudeste (SP, RJ, MG, PR, SC, RS, ES) | SVRS |
| SVC-AN | Contingência Nacional | SVC-AN |
| SVC-RS | Contingência Regional | SVC-RS |
| SEFAZ-SP | São Paulo (specific products) | SP |
| SEFAZ-MG | Minas Gerais | MG |
| SEFAZ-RS | Rio Grande do Sul | RS |
| SEFAZ-PR | Paraná | PR |
| SEFAZ-SC | Santa Catarina | SC |
| SEFAZ-RJ | Rio de Janeiro | RJ |
| SEFAZ-ES | Espírito Santo | ES |
| SEFAZ-BA | Bahia | BA |
| SEFAZ-PE | Pernambuco | PE |
| SEFAZ-CE | Ceará | CE |
| SEFAZ-AM | Amazonas | AM |

**Routing logic**: `autorizador = ROUTING_TABLE[emitter.state] ?? 'SVRS'`

### 1.3 SEFAZ Web Services

| Operation | SOAP Action | Endpoint Suffix | Description |
|-----------|-------------|-----------------|-------------|
| `NfeStatusServico` | `nfeStatusServicoNF` | `NFeStatusServico4` | Health check — call before first daily submission |
| `NfeAutorizacao` | `nfeAutorizacaoNF` | `NFeAutorizacao4` | Submit NFe XML for authorization |
| `NfeRetAutorizacao` | `nfeRetAutorizacaoNF` | `NFeRetAutorizacao4` | Poll for authorization result |
| `NfeConsultaProtocolo` | `nfeConsultaProtocoloNF` | `NFeConsultaProtocolo4` | Query protocol by chave de acesso |
| `NfeInutilizacao` | `nfeInutilizacaoNF` | `NFeInutilizacao4` | Invalidate number range |
| `RecepcaoEvento` | `recepcaoEventoNF` | `NFeRecepcaoEvento4` | Submit events (cancel, CC-e, EPEC) |
| `NfeDistribuicaoDFe` | `nfeDistDFeInteresse` | `NFeDistribuicaoDFe` | Distribute DF-e documents |

**Endpoint pattern**: `https://nfe.{autorizador}.fazenda.gov.br/NFeService4/NFeAutorizacao4`

### 1.4 Status Codes & Processing

| Code (cStat) | Meaning | Action |
|--------------|---------|--------|
| 100 | Autorizado (authorized) | Store protocol, emit `nfe.authorized` event |
| 101 | Cancelado (cancelled) | Confirm cancellation, emit `nfe.cancelled` event |
| 103 | Lote recebido (batch received) | Start polling NfeRetAutorizacao |
| 104 | Lote processado (batch processed) | Process individual NFe results |
| 105 | Lote em processamento (batch processing) | Continue polling (max 5 min) |
| 106 | Lote não localizado (batch not found) | Log error, may need resubmission |
| 150 | Lote processado com sucesso | All NFe in batch authorized |
| 201 | Rejeição: erro schemas | Fix XML, resubmit |
| 202 | Rejeição: nf-e não localizada | Query by chave de acesso |
| 203 | Rejeição: nf-e já autorizada | Duplicate — treat as success |
| 204 | Rejeição: nf-e duplicada | Duplicate — treat as success |
| 205 | Rejeição: nf-e cancelada | Already cancelled |
| 206 | Rejeição: inconsistência fiscal | Fix data, resubmit |
| 207 | Rejeição: NF-e com形势 | Check形势 codes |
| 238 | Rejeição: serviço indisponível | SEFAZ down — activate EPEC contingency |
| 239 | Rejeição: timeout | Retry with exponential backoff |
| 562 | Rejeição: regras de validação | Business rule violation — fix and resubmit |
| 999 | Rejeição: erro não catalogado | Log full response, alert human review |

**Processing flow**:
```
NfeStatusServico → NfeAutorizacao → NfeRetAutorizacao (poll) → NfeConsultaProtocolo
                           ↓ failure
                    RecepcaoEvento (EPEC contingency)
```

---

## 2. NFe XML Schema — Full Structure

### 2.1 Root Structure (nfeProc)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe> ... </NFe>
  <protNFe>
    <infProt>
      <tpAmb>1</tpAmb>          <!-- 1=produção, 2=homologação -->
      <verAplic>SVRS20250101</verAplic>
      <chNFe>35250712345678000199550010000001231234567890</chNFe>
      <dhRecbto>2025-07-01T10:30:00-03:00</dhRecbto>
      <nProt>135250000001234</nProt>
      <digVal>abc123...</digVal>  <!-- SHA-256 hash of NFe content -->
      <cStat>100</cStat>
      <xMotivo>Autorizado o uso da NF-e</xMotivo>
    </infProt>
  </protNFe>
</nfeProc>
```

### 2.2 infNFe — Information Block

```xml
<NFe>
  <infNFe versao="4.00" Id="NFe35250712345678000199550010000001231234567890">
    <ide>         <!-- Identification -->
    <emit>        <!-- Emitter (seller) -->
    <avulsa>      <!-- Avulsa (optional, government use) -->
    <dest>        <!-- Destination (buyer) -->
    <retirada>    <!-- Pickup address (optional) -->
    <entrega>     <!-- Delivery address (optional) -->
    <autXML>      <!-- Authorized XML readers (optional) -->
    <det nItem="1"> <!-- Items (1..990) -->
    <total>       <!-- Totals -->
    <transp>      <!-- Transport -->
    <cobr>        <!-- Billing (boletos) -->
    <pag>         <!-- Payment -->
    <infIntermed> <!-- Intermediary (optional) -->
    <infAdic>     <!-- Additional info (optional) -->
    <exporta>     <!-- Export (optional) -->
    <compra>      <!-- Purchase order (optional) -->
    <cana>        <!-- Sugar cane (optional) -->
    <infRespTec>  <!-- Responsible technician (optional) -->
    <infSolicNFF> <!-- NFF request (optional) -->
  </infNFe>
</NFe>
```

### 2.3 ide — Identification Block

```xml
<ide>
  <cUF>35</cUF>                          <!-- State code (IBGE) -->
  <natOp>VENDA DE MERCADORIA</natOp>     <!-- Operation nature -->
  <mod>55</mod>                           <!-- Model: 55=NFe, 65=NFC-e -->
  <serie>1</serie>                        <!-- Series (1-999) -->
  <nNF>123</nNF>                          <!-- Number (1-999999999) -->
  <dhEmi>2025-07-01T10:00:00-03:00</dhEmi>   <!-- Issue date -->
  <dhSaiEnt>2025-07-01T14:00:00-03:00</dhSaiEnt> <!-- Exit date (obrigatório) -->
  <tpNF>1</tpNF>                          <!-- 0=entrada, 1=saída -->
  <idDest>1</idDest>                      <!-- 1=interna, 2=interestadual, 3=exterior -->
  <cMunFG>3550308</cMunFG>               <!-- City code (IBGE 7 dígitos) -->
  <tpImp>1</tpImp>                        <!-- Print type: 1=normal -->
  <tpEmis>1</tpEmis>                      <!-- Emission: 1=normal, 9=EPEC -->
  <cDV>0</cDV>                            <!-- Check digit (last of 44-digit chave) -->
  <tpAmb>1</tpAmb>                        <!-- 1=produção, 2=homologação -->
  <finNFe>1</finNFe>                      <!-- 1=normal, 2=ajuste, 4=devolução -->
  <indFinal>1</indFinal>                  <!-- 0=normal, 1=consumidor final -->
  <indPres>1</indPres>                    <!-- Presence: 1=operação presencial -->
  <indIntermed>0</indInterMed>            <!-- 0=não intermediador -->
  <procEmi>0</procEmi>                    <!-- 0=processado pelo emitente -->
  <verProc>1.0.0</verProc>               <!-- Emitter software version -->
</ide>
```

### 2.4 emit — Emitter Block

```xml
<emit>
  <CNPJ>12345678000199</CNPJ>
  <xNome>EMPRESA LTDA</xNome>
  <xFant>FANTASIA</xFant>
  <enderEmit>
    <xLgr>Rua Exemplo</xLgr>
    <nro>100</nro>
    <xCpl>Sala 1</xCpl>
    <xBairro>Centro</xBairro>
    <cMun>3550308</cMun>
    <xMun>São Paulo</xMun>
    <UF>SP</UF>
    <CEP>01001000</CEP>
    <cPais>001058</cPais>
    <xPais>BRASIL</xPais>
    <fone>1112345678</fone>
  </enderEmit>
  <IE>123456789012</IE>                   <!-- Inscrição Estadual -->
  <CRT>1</CRT>                            <!-- 1=Simples Nacional, 2=Excessao, 3=Normal -->
</emit>
```

### 2.5 dest — Destination Block

```xml
<dest>
  <CNPJ>98765432000188</CNPJ>
  <!-- OR <CPF>12345678901</CPF> for PF -->
  <xNome>CLIENTE LTDA</xNome>
  <enderDest>
    <xLgr>Av. Cliente</xGr>
    <nro>200</nro>
    <xBairro>Vila Cliente</xBairro>
    <cMun>3550308</cMun>
    <xMun>São Paulo</xMun>
    <UF>SP</UF>
    <CEP>02002000</CEP>
    <cPais>001058</cPais>
    <xPais>BRASIL</xPais>
  </enderDest>
  <indIEDest>9</indIEDest>               <!-- 1=contribuinte, 2=isento, 9=não contribuinte -->
  <IE>...</IE>                            <!-- Required if indIEDest=1 -->
  <ISUF>...</ISUF>                        <!-- Optional -->
  <IM>...</IM>                            <!-- Inscrição Municipal (if applicable) -->
  <email>cliente@email.com</email>
</dest>
```

### 2.6 det — Item Details (repeatable nItem=1..990)

```xml
<det nItem="1">
  <prod>
    <cProd>001</cProd>                      <!-- Product code (emitter) -->
    <cEAN>SEM GTIN</cEAN>                   <!-- EAN-13 or "SEM GTIN" -->
    <xProd>Produto Exemplo</xProd>
    <NCM>61091000</NCM>                     <!-- NCM code (8 digits) -->
    <CEST>21.058.00</CEST>                  <!-- Optional CEST -->
    <indEscala>N</indEscale>                <!-- N=VFR, S=VND atacadista -->
    <CFOP>5102</CFOP>                       <!-- Operation code -->
    <uCom>UN</uCom>                         <!-- Unit of measure -->
    <qCom>10.0000</qCom>                    <!-- Quantity (4 decimal places) -->
    <vUnCom>100.0000000000</vUnCom>         <!-- Unit value (10 decimal places) -->
    <vProd>1000.00</vProd>                  <!-- Total product value -->
    <cEANTrib>SEM GTIN</cEANTrib>
    <uTrib>UN</uTrib>
    <qTrib>10.0000</qTrib>
    <vUnTrib>100.0000000000</vUnTrib>
    <vFrete>0.00</vFrete>                   <!-- Freight (if freight on item) -->
    <vSeg>0.00</vSeg>                       <!-- Insurance -->
    <vDesc>0.00</vDesc>                     <!-- Discount -->
    <vOutro>0.00</vOutro>                   <!-- Other expenses -->
    <indTot>1</indTot>                      <!-- 1=compõe total, 0=não compõe -->
    <xPed>Pedido 123</xPed>                 <!-- Purchase order reference -->
    <nItemPed>1</nItemPed>                  <!-- Item number in PO -->
    <nFCI>...</nFCI>                        <!-- FCI number (if applicable) -->
  </prod>
  <imposto>
    <!-- Tax block (see §2.7) -->
  </imposto>
  <infAdFisco>...</infAdFisco>              <!-- Fiscal additional info (optional) -->
</det>
```

### 2.7 imposto — Tax Block (per item)

```xml
<imposto>
  <vTotTrib>180.00</vTotTrib>               <!-- Total tributes (estimate) -->
  
  <!-- ICMS (state tax on goods) -->
  <ICMS>
    <ICMS00>                               <!-- Different ICMS groups exist -->
      <orig>0</orig>                        <!-- Origin: 0=nacional, 1..8=imported variants -->
      <CST>00</CST>                         <!-- CST code (00-90) -->
      <modBC>0</modBC>                      <!-- BC calc method: 0=margem valor add -->
      <vBC>1000.00</vBC>                    <!-- Base value -->
      <pICMS>18.00</pICMS>                  <!-- Rate (%) -->
      <vICMS>180.00</vICMS>                 <!-- Tax value -->
    </ICMS00>
  </ICMS>

  <!-- IPI (federal tax on industrial products) -->
  <IPI>
    <clEnq>...</clEnq>                      <!-- Optional classification -->
    <CNPJProd>...</CNPJProd>                <!-- Optional manufacturer CNPJ -->
    <cSelo>...</cSelo>                      <!-- Optional seal code -->
    <qSelo>...</qSelo>                      <!-- Optional seal quantity -->
    <cEnq>999</cEnq>                       <!-- Enquadramento code (999=default) -->
    <IPINT>
      <CST>53</CST>                         <!-- CST for non-taxed IPI -->
    </IPINT>
  </IPI>

  <!-- PIS (social contribution) -->
  <PIS>
    <PISAliq>
      <CST>01</CST>                         <!-- CST code -->
      <vBC>1000.00</vBC>
      <pPIS>1.65</pPIS>                     <!-- Rate -->
      <vPIS>16.50</vPIS>
    </PISAliq>
  </PIS>

  <!-- COFINS (social contribution) -->
  <COFINS>
    <COFINSAliq>
      <CST>01</CST>
      <vBC>1000.00</vBC>
      <pCOFINS>7.60</pCOFINS>
      <vCOFINS>76.00</vCOFINS>
    </COFINSAliq>
  </COFINS>
</imposto>
```

### 2.8 total — Totals Block

```xml
<total>
  <ICMSTot>
    <vBC>1000.00</vBC>                     <!-- ICMS base -->
    <vICMS>180.00</vICMS>                  <!-- ICMS total -->
    <vICMSDeson>0.00</vICMSDeson>          <!-- ICMS desonerado -->
    <vFCPUFDest>0.00</vFCPUFDest>          <!-- FCP for DIFAL -->
    <vICMSUFDest>0.00</vICMSUFDest>        <!-- ICMS DIFAL UF destino -->
    <vICMSUFRemet>0.00</vICMSUFRemet>      <!-- ICMS DIFAL UF remetente -->
    <vBCST>0.00</vBCST>                    <!-- ICMS-ST base -->
    <vST>0.00</vST>                        <!-- ICMS-ST total -->
    <vProd>1000.00</vProd>                 <!-- Product total -->
    <vFrete>0.00</vFrete>                  <!-- Freight -->
    <vSeg>0.00</vSeg>                      <!-- Insurance -->
    <vDesc>0.00</vDesc>                    <!-- Discount -->
    <vII>0.00</vII>                        <!-- Import tax -->
    <vIPI>0.00</vIPI>                      <!-- IPI total -->
    <vPIS>16.50</vPIS>                     <!-- PIS total -->
    <vCOFINS>76.00</vCOFINS>               <!-- COFINS total -->
    <vOutro>0.00</vOutro>                  <!-- Other expenses -->
    <vNF>1000.00</vNF>                     <!-- NFe total -->
    <vTotTrib>180.00</vTotTrib>            <!-- Total tributes estimate -->
  </ICMSTot>
  <ISSQNtot>                               <!-- ISSQN total (services) -->
    <vServ>0.00</vServ>                    <!-- Services value -->
    <vBC>0.00</vBC>                        <!-- ISS base -->
    <vISS>0.00</vISS>                      <!-- ISS total -->
    <vPIS>0.00</vPIS>
    <vCOFINS>0.00</vCOFINS>
  </ISSQNtot>
  <retTrib>                                <!-- Retained taxes (optional) -->
    <vRetPIS>0.00</vRetPIS>
    <vRetCOFINS>0.00</vRetCOFINS>
    <vRetCSLL>0.00</vRetCSLL>
    <vBCIRRF>0.00</vBCIRRF>
    <vIRRF>0.00</vIRRF>
    <vBCRetPrev>0.00</vBCRetPrev>
    <vRetPrev>0.00</vRetPrev>
  </retTrib>
</total>
```

### 2.9 pag — Payment Block

```xml
<pag>
  <indPag>0</indPag>                       <!-- 0=without, 1=cash, 2=credit, 3=debit -->
  <tPag>01</tPag>                          <!-- Payment type: 01=dinheiro, 02=cheque, 03=cartão crédito -->
  <vPag>1000.00</vPag>                     <!-- Payment value -->
  <card>                                   <!-- Card details (if tPag=03/04) -->
    <tpIntegra>1</tpIntegra>               <!-- 1=integrado, 2=terminal, 3=outros -->
    <CNPJ>...</CNPJ>
    <tBand>01</tBand>                      <!-- 01=visa, 02=master, 03=amex -->
    <cAut>...</cAut>                       <!-- Authorization code -->
  </card>
  <troco>0.00</troco>                      <!-- Change (if applicable) -->
</pag>
```

### 2.10 Chave de Acesso — 44 Digit Generation

The `chave de acesso` (access key) uniquely identifies each NFe:

```
Format: UF(2) + AAMM(4) + CNPJ(14) + MOD(2) + SERIE(3) + NUM(9) + EMIS(1) + NUM(8) + DV(1)
Example: 35 2507 12345678000199 55 001 000000123 1 00000012 3
Total: 44 digits
```

**Generation logic**:
1. `UF` = state code (2 digits, IBGE)
2. `AAMM` = YYMM of issue date
3. `CNPJ` = emitter's CNPJ (14 digits)
4. `MOD` = model (55 for NFe, 65 for NFC-e)
5. `SERIE` = series (3 digits, zero-padded)
6. `NUM` = number (9 digits, zero-padded)
7. `EMIS` = emission type (1 digit: 1=normal)
8. `NUM` = sequential number (8 digits)
9. `DV` = check digit (modulo 11 of concatenation without DV)

---

## 3. Digital Certificate Management

### 3.1 Certificate Types

| Type | Format | Storage | Hardware | Use Case |
|------|--------|---------|----------|----------|
| **A1** | .pfx / .p12 | File-based | No | Small businesses, easy deployment |
| **A2** | .pfx / .p12 | File-based | No (cloud KMS) | Cloud-first, managed |
| **A3** | Smart card / USB token | Hardware | Yes | Enterprise, high-security |

**MVP scope**: A1 only (file upload). A3 requires PKCS#11 driver integration.

### 3.2 Certificate Loading (Python)

```python
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
from cryptography.hazmat.primitives import hashes
from cryptography import x509

class CertificateManager:
    def load_pfx(self, pfx_path: str, password: bytes) -> dict:
        """Load A1/A2 PFX certificate. Returns private key + cert chain."""
        with open(pfx_path, "rb") as f:
            pfx_data = f.read()
        
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data, password
        )
        
        return {
            "private_key": private_key,
            "certificate": certificate,
            "chain": additional_certs or [],
            "subject_cn": certificate.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value,
            "issuer_cn": certificate.issuer.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value,
            "not_valid_before": certificate.not_valid_before_utc,
            "not_valid_after": certificate.not_valid_after_utc,
            "serial_number": str(certificate.serial_number),
            "thumbprint": certificate.fingerprint(hashes.SHA256()).hex(),
        }
```

### 3.3 XML Signing (XMLDSig)

NFe XML must be signed with the emitter's digital certificate per SEFAZ requirements:

```python
import lxml.etree as etree
from signxml import XMLSigner, methods

class NFeSigner:
    def sign(self, nfe_xml: etree._Element, certificate_pem: bytes, private_key_pem: bytes) -> etree._Element:
        """Sign NFe XML with SHA-256 digest and RSA-2048."""
        
        # Find the infNFe element (must be signed)
        inf_nfe = nfe_xml.find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
        inf_nfe_id = inf_nfe.get("Id")
        
        # Sign the infNFe element (not the entire document)
        signer = XMLSigner(
            method=methods.enveloped,
            signature_algorithm="rsa-sha256",
            digest_algorithm="sha256",
            c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
        )
        
        signed_xml = signer.sign(
            nfe_xml,
            key=private_key_pem,
            cert=[certificate_pem],
            reference_uri=f"#{inf_nfe_id}",
        )
        
        return signed_xml
```

**Signing rules**:
- Only `infNFe` is signed (identified by `Id` attribute)
- Digest: SHA-256
- Signature algorithm: RSA-2048
- Canonicalization: Exclusive XML C14N
- The `SignatureValue` goes inside `<infNFe>` element (not outside)
- The signed NFe is then embedded in the SOAP envelope

### 3.4 Certificate Renewal

```python
class CertificateRenewal:
    """Monitor certificate expiry and trigger renewal workflow."""
    
    RENEWAL_WARN_DAYS = 30   # Warn 30 days before expiry
    RENEWAL_BLOCK_DAYS = 0   # Block operations on expiry day
    
    def check_expiry(self, certificate: dict) -> dict:
        days_until_expiry = (certificate["not_valid_after"] - datetime.now(UTC)).days
        
        if days_until_expiry <= 0:
            return {"status": "expired", "action": "block", "days": days_until_expiry}
        elif days_until_expiry <= self.RENEWAL_WARN_DAYS:
            return {"status": "warning", "action": "notify", "days": days_until_expiry}
        else:
            return {"status": "valid", "action": "none", "days": days_until_expiry}
```

### 3.5 Secure Storage

```sql
CREATE TABLE digital_certificates (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  display_name    TEXT NOT NULL,
  cert_type       TEXT NOT NULL,            -- 'A1', 'A2', 'A3'
  pfx_encrypted   BLOB NOT NULL,            -- Encrypted PFX (AES-256-GCM)
  pfx_iv          BLOB NOT NULL,            -- Initialization vector
  subject_cn      TEXT NOT NULL,
  issuer_cn       TEXT NOT NULL,
  serial_number   TEXT NOT NULL,
  thumbprint      TEXT NOT NULL,
  not_valid_before TIMESTAMP WITH TIME ZONE NOT NULL,
  not_valid_after  TIMESTAMP WITH TIME ZONE NOT NULL,
  is_active       INTEGER DEFAULT 1,
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (tenant_id, thumbprint)
);

CREATE INDEX idx_cert_tenant ON digital_certificates(tenant_id);
CREATE INDEX idx_cert_expiry ON digital_certificates(not_valid_after);
```

---

## 4. NFS-e Architecture — ABRASF Standard

### 4.1 ABRASF Standard Overview

NFS-e uses the **ABRASF** (Associação Brasileira das Secretarias de Fazenda das Capitais) standard:

| Version | Year | Key Features |
|---------|------|--------------|
| ABRASF 2.01 | 2011 | Basic RPS flow |
| ABRASF 2.02 | 2013 | Substitution of RPS |
| ABRASF 2.03 | 2014 | Additional fields, SP adoption |
| ABRASF 2.04 | 2017 | Current standard, RJ adoption |

**RPS Flow**:
```
RPS (Recibo Provisório de Serviços) → Send to SEFAZ → NFS-e (official receipt)
     ↑ issued by emitter                 ↓ returned with protocol
     ↓ stored locally                    ↓ displayed on municipal portal
```

### 4.2 Municipal Variations

| City | ABRASF | ISS Rates | RPS Flow | Notes |
|------|--------|-----------|----------|-------|
| **São Paulo** | 2.03 | 2-5% by CNAE | RPS→NFS-e (same day) | SEFAZ-SP, well-documented |
| **Rio de Janeiro** | 2.04 | 2-5% by CNAE | RPS→NFS-e (batch) | Different RPS flow, XML schema differences |
| **Belo Horizonte** | 2.03 | 2-5% by CNAE | RPS→NFS-e | Specific construction rules |
| **Curitiba** | 2.03 | 2-5% by CNAE | RPS→NFS-e | |
| **Brasília** | 2.03 | 2-5% by CNAE | RPS→NFS-e | |
| **Salvador** | 2.04 | 2-5% by CNAE | RPS→NFS-e | |
| **Fortaleza** | 2.03 | 2-5% by CNAE | RPS→NFS-e | |
| **Manaus** | 2.02 | 2-5% by CNAE | RPS→NFS-e | |
| **Recife** | 2.03 | 2-5% by CNAE | RPS→NFS-e | |
| **Porto Alegre** | 2.03 | 2-5% by CNAE | RPS→NFS-e | |

### 4.3 Pluggable Municipality Architecture

```python
class MunicipalityConfig(ABC):
    """Base class for municipality-specific NFS-e configuration."""
    
    @abstractmethod
    def get_webservice_url(self, environment: str) -> str:
        """Return SEFAZ endpoint URL."""
        
    @abstractmethod
    def get_abrasf_version(self) -> str:
        """Return ABRASF version (e.g., '2.03')."""
    
    @abstractmethod
    def get_iss_rate(self, cnae_code: str) -> Decimal:
        """Return ISS rate for given CNAE code."""
    
    @abstractmethod
    def get_xml_template(self) -> str:
        """Return municipality-specific XML template."""
    
    @abstractmethod
    def validate_rps(self, rps: dict) -> list[str]:
        """Municipality-specific RPS validation rules."""
    
    def get_soap_action(self, operation: str) -> str:
        """Default ABRASF SOAP action. Override if municipality deviates."""
        return f"abrasi://ws.gov.br/{operation}"


class SaoPauloMunicipality(MunicipalityConfig):
    """São Paulo NFS-e implementation (ABRASF 2.03)."""
    
    WEBSERVICE_URLS = {
        "producao": "https://nfe.prefeitura.sp.gov.br/ws/nfe.svc",
        "homologacao": "https://homologacao.nfe.prefeitura.sp.gov.br/ws/nfe.svc",
    }
    
    def get_webservice_url(self, environment: str) -> str:
        return self.WEBSERVICE_URLS[environment]
    
    def get_abrasf_version(self) -> str:
        return "2.03"
    
    def get_iss_rate(self, cnae_code: str) -> Decimal:
        # SP ISS rates by CNAE
        RATES = {
            "5411": Decimal("0.02"),   # IT consulting: 2%
            "6201": Decimal("0.02"),   # Software dev: 2%
            "7020": Decimal("0.05"),   # Management consulting: 5%
            "8599": Decimal("0.05"),   # Other education: 5%
        }
        return RATES.get(cnae_code[:4], Decimal("0.05"))  # Default 5%


class RioJaneiroMunicipality(MunicipalityConfig):
    """Rio de Janeiro NFS-e implementation (ABRASF 2.04)."""
    
    WEBSERVICE_URLS = {
        "producao": "https://www4.nfrj.gov.br/wsnfe/NFeService4",
        "homologacao": "https://www4.nfrj.gov.br/wsnfe/NFeService4",
    }
    
    def get_abrasf_version(self) -> str:
        return "2.04"
    
    # ... additional overrides
```

### 4.4 Municipality Registry

```sql
CREATE TABLE municipality_configs (
  id                  TEXT PRIMARY KEY,
  ibge_code           TEXT NOT NULL UNIQUE,    -- 7-digit IBGE code
  city_name           TEXT NOT NULL,
  state_code          TEXT NOT NULL,
  abrasf_version      TEXT NOT NULL,           -- '2.01', '2.02', '2.03', '2.04'
  webservice_url_prod TEXT NOT NULL,
  webservice_url_hml  TEXT NOT NULL,
  iss_rates_cnae_json JSONB NOT NULL,          -- { "CNAE4": rate }
  rps_schema_version  TEXT NOT NULL,           -- municipality-specific schema
  is_active           INTEGER DEFAULT 1,
  added_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  notes               TEXT
);

-- Pre-populated for top 100 municipalities
INSERT INTO municipality_configs (ibge_code, city_name, state_code, ...) VALUES
  ('3550308', 'São Paulo', 'SP', '2.03', ...),
  ('3304557', 'Rio de Janeiro', 'RJ', '2.04', ...),
  ('3106200', 'Belo Horizonte', 'MG', '2.03', ...),
  -- ... top 100
```

---

## 5. NFS-e XML Structure (ABRASF Standard)

### 5.1 RPS (Recibo Provisório de Serviços)

```xml
<CompNFe xmlns="http://www.abrasf.org.br/abasi/types" versao="2.03">
  <InfNFe>
    <NumeroRPS>12345</NumeroRPS>
    <SerieRPS>A</SerieRPS>
    <TipoRPS>1</TipoRPS>                      <!-- 1=RPS, 2=RPS-M, 3=RPS-E -->
    <DataEmissaoRPS>2025-07-01T10:00:00</DataEmissaoRPS>
    <StatusRPS>1</StatusRPS>                  <!-- 1=Normal, 2=Cancelado, 3=Inutilizado -->
    
    <!-- Prestador de Serviços (Provider) -->
    <PrestadorServico>
      <CNPJ>12345678000199</CNPJ>
      <InscricaoMunicipal>12345678</InscricaoMunicipal>
      <RazaoSocial>EMPRESA LTDA</RazaoSocial>
      <Endereco>
        <TipoLogradouro>Rua</TipoLogradouro>
        <Logradouro>Rua Exemplo</Logradouro>
        <Numero>100</Numero>
        <Complemento>Sala 1</Complemento>
        <Bairro>Centro</Bairro>
        <CodigoMunicipio>3550308</CodigoMunicipio>
        <Uf>SP</Uf>
        <Cep>01001000</Cep>
      </Endereco>
      <Telefone>1112345678</Telefone>
      <Email>empresa@email.com</Email>
    </PrestadorServico>
    
    <!-- Tomador de Serviços (Client) -->
    <TomadorServico>
      <RazaoSocial>CLIENTE LTDA</RazaoSocial>
      <CNPJ>98765432000188</CNPJ>
      <!-- OR <CPF>12345678901</CPF> -->
      <Endereco>
        <TipoLogradouro>Av</TipoLogradouro>
        <Logradouro>Av. Cliente</Logradouro>
        <Numero>200</Numero>
        <Bairro>Vila Cliente</Bairro>
        <CodigoMunicipio>3550308</CodigoMunicipio>
        <Uf>SP</Uf>
        <Cep>02002000</Cep>
      </Endereco>
    </TomadorServico>
    
    <!-- Serviços -->
    <ListaServicos>
      <ItemListaServico>
        <Descricao>Consultoria em TI</Descricao>
        <QuantidadeServico>10</QuantidadeServico>
        <ValorServico>5000.00</ValorServico>
        <ValorDeducoes>0.00</ValorDeducoes>
        <ValorOutrasRetencoes>0.00</ValorOutrasRetencoes>
        <BaseCalculo>5000.00</BaseCalculo>
        <Aliquota>2.00</Aliquota>                <!-- 2% ISS for IT services in SP -->
        <ValorIss>100.00</ValorIss>
        <ItemListaServico>14.01</ItemListaServico> <!-- LC 116 item code -->
        <CNAEServico>6201501</CNAEServico>         <!-- CNAE code -->
        <Tributavel>S</Tributavel>                  <!-- S=taxable, N=exempt -->
      </ItemListaServico>
    </ListaServicos>
    
    <!-- Valores Totais -->
    <ValoresTotaisRPS>
      <ValorServicos>5000.00</ValorServicos>
      <ValorDeducoes>0.00</ValorDeducoes>
      <ValorPIS>0.00</ValorPIS>
      <ValorCOFINS>0.00</ValorCOFINS>
      <ValorIR>0.00</ValorIR>
      <ValorCSLL>0.00</ValorCSLL>
      <ValorISS>100.00</ValorISS>
      <ValorBCPIS>0.00</ValorBCPIS>
      <ValorBCCOFINS>0.00</ValorBCCOFINS>
      <ValorBCIR>0.00</ValorBCIR>
      <ValorBCCSLL>0.00</ValorBCCSLL>
      <ValorBCISS>5000.00</ValorBCISS>
    </ValoresTotaisRPS>
    
    <!-- Observações -->
    <Observacoes>Nota referente a serviços de consultoria</Observacoes>
  </InfNFe>
</CompNFe>
```

### 5.2 NFS-e Response (After Authorization)

```xml
<ConsultaNFeResposta xmlns="http://www.abrasf.org.br/abasi/types">
  <ConsultaNFeResult>
    <CompNFe>
      <InfNFe>
        <!-- Same as RPS, plus: -->
        <NumeroNFe>67890</NumeroNFe>
        <SerieNFe>A</SerieNFe>
        <DataEmissaoNFe>2025-07-01T10:05:00</DataEmissaoNFe>
        <ChaveNFe>35202507000000123456780001995001000000123456</ChaveNFe>
        <ProtocoloNFe>1.3525070000000123456</ProtocoloNFe>
        <LinkNFEdanfse>https://nfe.prefeitura.sp.gov.br/nfe/</LinkNFEdanfse>
      </InfNFe>
    </CompNFe>
  </ConsultaNFeResult>
</ConsultaNFeResposta>
```

---

## 6. Contingency Mode — EPEC

### 6.1 When to Activate EPEC

**EPEC** (Evento Prévio de Emissão em Contingência) is activated when:

1. SEFAZ autorizador is down (HTTP timeout, 503, SOAP fault with code 238/239)
2. `NfeStatusServico` fails for >5 minutes
3. Manual activation by operator during planned SEFAZ maintenance

### 6.2 EPEC XML Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<envEPEC xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">
  <eventoEPEC>
    <infEPEC versao="1.00">
      <tpAmb>1</tpAmb>
      <xServ>EPEC</xServ>
      <dhEmiEvento>2025-07-01T10:00:00-03:00</dhEmiEvento>
      <tpEmis>9</tpEmis>                     <!-- 9 = EPEC -->
      <chNFe>35250712345678000199550010000001231234567890</chNFe>
      <CNPJ>12345678000199</CNPJ>
      <cUF>35</cUF>
      <UF>SP</UF>
      <mod>55</mod>
      <serie>1</serie>
      <nNF>123</nNF>
      <dhRecbto>2025-07-01T10:00:00-03:00</dhRecbto>
      <nProtEPEC>...</nProtEPEC>              <!-- Protocol from SEFAZ -->
    </infEPEC>
  </eventoEPEC>
</envEPEC>
```

### 6.3 Contingency Flow

```
Normal Flow:
  NfeAutorizacao → NfeRetAutorizacao → NfeConsultaProtocolo → Store authorized NFe

EPEC Flow:
  Detect SEFAZ down (timeout/fault)
  → Sign NFe with tpEmis=9 (EPEC)
  → Send eventoEPEC to SVC (contingency SEFAZ)
  → Receive EPEC protocol
  → Store NFe locally with status=epec_pending
  → When SEFAZ recovers:
     → Send full NFe via NfeAutorizacao
     → Match by chave de acesso
     → Update status from epec_pending to authorized
```

### 6.4 Contingency State Machine

```
                    ┌──────────────┐
                    │   NORMAL     │
                    └──────┬───────┘
                           │ SEFAZ down
                           ▼
                    ┌──────────────┐
                    │ EPEC_ACTIVE  │ ← Send EPEC, get protocol
                    └──────┬───────┘
                           │ SEFAZ recovered
                           ▼
                    ┌──────────────┐
                    │ RESUBMITTING │ ← Send full NFe via autorizacao
                    └──────┬───────┘
                           │ Success
                           ▼
                    ┌──────────────┐
                    │  AUTHORIZED  │ ← Final state
                    └──────────────┘
```

---

## 7. API Endpoints

### 7.1 NFe Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/nfe/issue` | Issue new NFe | admin, ap_clerk |
| `POST` | `/api/nfe/:id/cancel` | Cancel authorized NFe | admin |
| `POST` | `/api/nfe/:id/cce` | Send correction letter (Carta de Correção) | admin |
| `GET` | `/api/nfe/:id/status` | Query NFe status by chave de acesso | viewer |
| `GET` | `/api/nfe/list` | List NFe with filters | viewer |
| `GET` | `/api/nfe/:id/xml` | Download NFe XML (signed + protocol) | viewer |
| `GET` | `/api/nfe/:id/danfe` | Generate DANFE PDF | viewer |
| `POST` | `/api/nfe/inutilize` | Invalidate number range | admin |
| `POST` | `/api/nfe/contingency/epec` | Activate EPEC contingency | admin |
| `GET` | `/api/nfe/status-sefaz` | Check SEFAZ autorizador health | viewer |

### 7.2 NFS-e Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/nfse/issue` | Issue new NFS-e (RPS) | admin, ar_clerk |
| `POST` | `/api/nfse/:id/cancel` | Cancel NFS-e | admin |
| `GET` | `/api/nfse/:id/status` | Query NFS-e status | viewer |
| `GET` | `/api/nfse/list` | List NFS-e with filters | viewer |
| `GET` | `/api/nfse/:id/danfse` | Generate DANFSe PDF | viewer |
| `GET` | `/api/nfse/municipalities` | List supported municipalities | viewer |
| `POST` | `/api/nfse/municipalities/:ibge/enable` | Enable municipality for tenant | admin |

### 7.3 Shared Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/certificates/upload` | Upload digital certificate (A1 PFX) | admin |
| `GET` | `/api/certificates/list` | List tenant certificates | admin |
| `DELETE` | `/api/certificates/:id` | Delete certificate | admin |
| `GET` | `/api/certificates/:id/expiry` | Check certificate expiry status | admin |

### 7.4 Event Bus Events

| Event | Payload | Subscribers |
|-------|---------|-------------|
| `nfe.authorized` | `{ nfe_id, chave_acesso, protocolo, emitida_em }` | GL, Invoice, SPED |
| `nfe.cancelled` | `{ nfe_id, motivo, data_cancelamento }` | GL, Invoice |
| `nfe.rejected` | `{ nfe_id, cstat, xmotivo }` | Alert, Invoice |
| `nfe.epec_activated` | `{ nfe_ids, motivo }` | Alert, Operator |
| `nfse.authorized` | `{ nfse_id, numero_nfe, protocolo }` | GL, Invoice |
| `nfse.cancelled` | `{ nfse_id, motivo }` | GL, Invoice |
| `certificate.expiring` | `{ cert_id, days_until_expiry }` | Alert |
| `certificate.expired` | `{ cert_id }` | Alert, Block |

---

## 8. Database Schema — NFe/NFS-e Tables

```sql
-- NFe documents
CREATE TABLE nfe_documents (
  id                TEXT PRIMARY KEY,
  tenant_id         TEXT NOT NULL,
  chave_acesso      TEXT NOT NULL UNIQUE,     -- 44-digit chave de acesso
  numero            INTEGER NOT NULL,
  serie             INTEGER NOT NULL,
  modelo            INTEGER NOT NULL,          -- 55=NFe, 65=NFC-e
  emitente_cnpj     TEXT NOT NULL,
  destinatario_doc  TEXT,                      -- CNPJ or CPF
  natureza_operacao TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'draft',
  -- draft → signing → submitted → polling → authorized → cancelled
  -- draft → signing → epec_pending → submitted → authorized
  emission_type     INTEGER NOT NULL,          -- 1=normal, 9=EPEC
  autorizador       TEXT NOT NULL,             -- SVRS, SP, etc.
  ambiente          TEXT NOT NULL,             -- 'producao' or 'homologacao'
  valor_total       NUMERIC(18,2) NOT NULL,
  protocolo         TEXT,                      -- SEFAZ protocol number
  motivo_rejeicao   TEXT,                      -- Rejection reason (if any)
  xml_assinado      TEXT,                      -- Signed XML (stored)
  xml_autorizado    TEXT,                      -- Authorized XML (stored)
  danfe_pdf         BLOB,                      -- Generated DANFE
  emitida_em        TIMESTAMP WITH TIME ZONE,
  autorizada_em     TIMESTAMP WITH TIME ZONE,
  cancelada_em      TIMESTAMP WITH TIME ZONE,
  created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (tenant_id, numero, serie, modelo)
);

CREATE INDEX idx_nfe_tenant ON nfe_documents(tenant_id);
CREATE INDEX idx_nfe_chave ON nfe_documents(chave_acesso);
CREATE INDEX idx_nfe_status ON nfe_documents(tenant_id, status);

-- NFS-e documents
CREATE TABLE nfse_documents (
  id                TEXT PRIMARY KEY,
  tenant_id         TEXT NOT NULL,
  numero_rps        TEXT NOT NULL,
  serie_rps         TEXT NOT NULL,
  numero_nfe        TEXT,                      -- Official NFS-e number (after authorization)
  chave_nfe         TEXT,                      -- NFS-e access key
  protocolo         TEXT,
  ibge_code         TEXT NOT NULL,             -- Municipality IBGE code
  emitente_cnpj     TEXT NOT NULL,
  emitente_im       TEXT,                      -- Inscrição Municipal
  tomador_doc       TEXT,                      -- CNPJ or CPF of client
  tomador_razao     TEXT,
  status            TEXT NOT NULL DEFAULT 'draft',
  -- draft → submitted → authorized → cancelled
  valor_servicos    NUMERIC(18,2) NOT NULL,
  valor_iss         NUMERIC(18,2) NOT NULL,
  aliquota_iss      NUMERIC(5,2) NOT NULL,
  cnae_code         TEXT,
  item_lista_servico TEXT,                      -- LC 116 code
  xml_rps           TEXT,                      -- RPS XML
  xml_nfs_e         TEXT,                      -- Authorized NFS-e XML
  danfse_pdf        BLOB,                      -- Generated DANFSe
  emitida_em        TIMESTAMP WITH TIME ZONE,
  autorizada_em     TIMESTAMP WITH TIME ZONE,
  cancelada_em      TIMESTAMP WITH TIME ZONE,
  created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (tenant_id, numero_rps, serie_rps)
);

CREATE INDEX idx_nfse_tenant ON nfse_documents(tenant_id);
CREATE INDEX idx_nfse_ibge ON nfse_documents(tenant_id, ibge_code);
CREATE INDEX idx_nfse_status ON nfse_documents(tenant_id, status);

-- SEFAZ integration log
CREATE TABLE sefaz_audit_log (
  id              TEXT PRIMARY KEY,
  tenant_id       TEXT NOT NULL,
  document_type   TEXT NOT NULL,               -- 'nfe', 'nfse'
  document_id     TEXT NOT NULL,
  operation       TEXT NOT NULL,               -- 'authorize', 'cancel', 'cce', 'status'
  autorizador     TEXT NOT NULL,
  request_xml     TEXT,                        -- Request sent to SEFAZ
  response_xml    TEXT,                        -- Response from SEFAZ
  cstat           TEXT,                        -- SEFAZ status code
  xmotivo         TEXT,                        -- SEFAZ status message
  duration_ms     INTEGER,
  success         INTEGER NOT NULL,            -- 0=failed, 1=success
  created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_tenant ON sefaz_audit_log(tenant_id, document_type);
CREATE INDEX idx_audit_doc ON sefaz_audit_log(document_id);
```

---

## 9. Testing Strategy

### 9.1 XML Schema Validation

```python
import lxml.etree as etree

class NFeXMLValidator:
    def __init__(self, xsd_path: str):
        with open(xsd_path, "rb") as f:
            self.schema = etree.XMLSchema(etree.parse(f))
    
    def validate(self, xml_content: bytes) -> tuple[bool, list[str]]:
        """Validate NFe XML against XSD. Returns (is_valid, errors)."""
        try:
            doc = etree.fromstring(xml_content)
            if self.schema.validate(doc):
                return True, []
            else:
                errors = [str(e) for e in self.schema.error_log]
                return False, errors
        except etree.XMLSyntaxError as e:
            return False, [str(e)]
```

**Test files needed**:
- `schemas/nfe_v4.00.xsd` — Official SEFAZ NFe 4.00 schema
- `schemas/nfe_v4.00.tiposBasico.xsd` — Basic types
- `schemas/nfe_v4.00_consStatServ.xsd` — Status service
- `schemas/nfe_v4.00_envEvento.xsd` — Event (cancel, EPEC)

### 9.2 Mock SEFAZ Responses

```python
# tests/mocks/sefaz_responses.py

MOCK_AUTORIZACAO_SUCCESS = {
    "NFeRetAutorizacaoResponse": {
        "NFeRetAutorizacaoResult": {
            "tpAmb": "1",
            "verAplic": "SVRS20250101",
            "cStat": "104",
            "xMotivo": "Lote processado",
            "protNFe": [{
                "infProt": {
                    "tpAmb": "1",
                    "verAplic": "SVRS20250101",
                    "chNFe": "35250712345678000199550010000001231234567890",
                    "dhRecbto": "2025-07-01T10:05:00-03:00",
                    "nProt": "135250000001234",
                    "digVal": "abc123...",
                    "cStat": "100",
                    "xMotivo": "Autorizado o uso da NF-e"
                }
            }]
        }
    }
}

MOCK_DUPLICATE = {
    "NFeRetAutorizacaoResponse": {
        "NFeRetAutorizacaoResult": {
            "cStat": "104",
            "xMotivo": "Lote processado",
            "protNFe": [{
                "infProt": {
                    "chNFe": "35250712345678000199550010000001231234567890",
                    "cStat": "204",
                    "xMotivo": "Rejeição: NF-e duplicada"
                }
            }]
        }
    }
}

MOCK_SEFAZ_DOWN = {
    "NFeRetAutorizacaoResponse": {
        "NFeRetAutorizacaoResult": {
            "cStat": "238",
            "xMotivo": "Rejeição: Serviço indisponível"
        }
    }
}
```

### 9.3 Test Categories

| Category | Count | Scope |
|----------|-------|-------|
| **XML Schema Validation** | ~50 | Every generated XML validated against XSD |
| **Chave de Acesso** | ~10 | Check digit, format, uniqueness |
| **Certificate Loading** | ~15 | PFX parsing, expiry, chain validation |
| **XML Signing** | ~10 | Signature generation, verification, tamper detection |
| **SEFAZ Client** | ~30 | SOAP requests, response parsing, error handling |
| **Autorizador Routing** | ~15 | State→autorizador mapping, fallback |
| **Status Code Handling** | ~25 | Every cStat code mapped correctly |
| **EPEC Contingency** | ~10 | Activation, resubmission, state transitions |
| **NFS-e RPS Generation** | ~20 | ABRASF XML structure, municipality variations |
| **NFS-e Municipal Variations** | ~30 | SP, RJ, BH specific rules |
| **Integration Tests** | ~20 | End-to-end issue/cancel flow |
| **Total** | ~235 | |

### 9.4 SEFAZ Homologação Testing

SEFAZ provides homologação (staging) environments:

| Autorizador | Homologação URL | Notes |
|-------------|-----------------|-------|
| SVRS | `https://homologacao.nfe.svrs.rs.gov.br/ws/...` | Most states use this |
| SVAN | `https://homologacao.sefazvirtual.fazenda.gov.br/NFeService4/...` | Nacional |
| SEFAZ-SP | `https://homologacao.nfe.fazenda.sp.gov.br/ws/nfe.svc` | SP specific |
| SEFAZ-RJ | `https://homologacao.nfrj.gov.br/wsnfe/NFeService4` | RJ specific |

**Testing rules**:
- Use CNPJ 00.000.000/0001-91 (dummy) in homologação
- Number ranges must be within authorized homologação ranges
- All XML signed with test certificates
- Results do NOT have legal effect

---

## 10. Error Handling & Retry Logic

### 10.1 SEFAZ Error Classification

```python
class SEFAZErrorClassification:
    """Classify SEFAZ errors for retry/escalation decisions."""
    
    RETRY_ERRORS = {105, 239}                  # Processing, timeout
    NO_RETRY_ERRORS = {201, 202, 204, 205}    # Schema, not found, duplicate
    ESCALATE_ERRORS = {238, 999}               # Service unavailable, unknown
    EPEC_ERRORS = {238, 239}                   # Errors that trigger contingency
    
    def classify(self, cstat: int) -> dict:
        if cstat in self.RETRY_ERRORS:
            return {"action": "retry", "backoff": "exponential", "max_attempts": 5}
        elif cstat in self.NO_RETRY_ERRORS:
            return {"action": "no_retry", "requires_fix": True}
        elif cstat in self.ESCALATE_ERRORS:
            return {"action": "escalate", "notify": True}
        elif cstat in self.EPEC_ERRORS:
            return {"action": "epec_contingency", "notify": True}
        else:
            return {"action": "unknown", "notify": True, "log_full_response": True}
```

### 10.2 Retry with Exponential Backoff

```python
import asyncio
from dataclasses import dataclass

@dataclass
class SEFAZRetryPolicy:
    max_attempts: int = 5
    base_delay_ms: int = 1000
    max_delay_ms: int = 60000
    jitter: bool = True
    
    async def retry_with_backoff(self, operation, cstat_classifier):
        for attempt in range(self.max_attempts):
            result = await operation()
            classification = cstat_classifier.classify(result.cstat)
            
            if classification["action"] in ("no_retry", "escalate"):
                return result
            
            if attempt < self.max_attempts - 1:
                delay = min(
                    self.base_delay_ms * (2 ** attempt),
                    self.max_delay_ms
                )
                if self.jitter:
                    delay = delay * random.uniform(0.5, 1.5)
                await asyncio.sleep(delay / 1000)
        
        # All retries exhausted — activate EPEC
        return result
```

---

## 11. Effort Estimate

### 11.1 NFe Module (Phase 2)

| Sub-feature | Effort (days) | Dependencies | Risk |
|-------------|---------------|--------------|------|
| SEFAZ SOAP client (SVRS only) | 5 | None | Medium |
| NFe 4.00 XML generator | 5 | None | Medium |
| Chave de acesso generation | 1 | None | Low |
| Digital certificate manager (A1) | 3 | None | Medium |
| XML signing (XMLDSig) | 3 | Certificate manager | High |
| Autorizador routing (all states) | 2 | SOAP client | Low |
| Status polling engine | 3 | SOAP client | Medium |
| Cancel + CC-e events | 2 | SOAP client, signing | Low |
| EPEC contingency mode | 4 | All above | High |
| Error handling + retry | 2 | All above | Medium |
| DANFE PDF generation | 3 | Authorized NFe | Low |
| NFe database schema + repository | 2 | None | Low |
| **NFe subtotal** | **35** | | |

### 11.2 NFS-e Module (Phase 1)

| Sub-feature | Effort (days) | Dependencies | Risk |
|-------------|---------------|--------------|------|
| ABRASF SOAP client | 3 | None | Medium |
| RPS XML generator (SP) | 3 | ABRASF client | Medium |
| São Paulo municipality config | 2 | RPS generator | Low |
| NFS-e authorization flow | 3 | ABRASF client | Medium |
| Pluggable municipality framework | 4 | ABRASF client | High |
| RJ municipality config | 2 | Framework | Medium |
| BH municipality config | 2 | Framework | Low |
| 7 additional municipalities | 7 | Framework | Medium |
| Top 100 municipalities (batch) | 10 | Framework | Medium |
| DANFSe PDF generation | 2 | Authorized NFS-e | Low |
| NFS-e database schema + repository | 2 | None | Low |
| **NFS-e subtotal** | **40** | | |

### 11.3 Testing & Integration

| Sub-feature | Effort (days) | Dependencies |
|-------------|---------------|--------------|
| XML schema validation suite | 3 | XSD files from SEFAZ |
| Mock SEFAZ responses | 2 | SOAP client |
| SEFAZ homologação integration tests | 5 | Full NFe stack |
| NFS-e integration tests | 3 | Full NFS-e stack |
| API endpoint tests | 3 | All modules |
| **Testing subtotal** | **16** | |

### 11.4 Summary

| Module | Effort | Priority |
|--------|--------|----------|
| NFS-e (Phase 1 — services-first) | 40 days | P1 |
| NFe (Phase 2 — goods) | 35 days | P2 |
| Testing & Integration | 16 days | Parallel |
| **Total** | **91 days** | |

### 11.5 Build Order

```
Week 1-2:   NFS-e ABRASF client + São Paulo config
Week 3-4:   NFS-e pluggable framework + RJ/BH configs
Week 5-6:   NFe SOAP client + XML generator + certificate manager
Week 7-8:   NFe XML signing + autorizador routing + polling
Week 9:     NFe cancel/CC-e + EPEC contingency
Week 10:    DANFE/DANFSe PDF generation
Week 11-12: Testing (schema validation, homologação, integration)
```

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SEFAZ downtime during peak periods | HIGH | EPEC contingency, async queue, monitoring |
| Municipal NFS-e fragmentation (5,570 cities) | HIGH | Pluggable framework, batch enablement, manual fallback |
| Digital certificate security breach | CRITICAL | Encrypted storage, HSM integration, access control |
| XML schema changes by SEFAZ | MEDIUM | XSD versioning, automated schema download, compatibility layer |
| Incorrect tax calculation → invalid NFe | HIGH | Integration with tax engine, XSD validation, golden master tests |
| A3 hardware token support complexity | MEDIUM | Defer A3 to post-MVP, focus on A1 |
| SOAP message size limits | LOW | Batch splitting, compression |

---

## 13. Key Files

```
services/cashflow/
├── src/
│   ├── nfe/
│   │   ├── sefaz_client.ts              # SEFAZ SOAP 1.2 client
│   │   ├── xml_generator.ts             # NFe XML 4.00 generator
│   │   ├── xml_signer.ts                # XMLDSig signing
│   │   ├── chave_acesso.ts              # 44-digit chave generation
│   │   ├── autorizador_router.ts        # State → autorizador mapping
│   │   ├── status_poller.ts             # NfeRetAutorizacao polling
│   │   ├── certificate_manager.ts       # PFX loading + validation
│   │   ├── contingency_epec.ts          # EPEC event generation
│   │   ├── danfe_renderer.ts            # DANFE PDF generation
│   │   ├── cancel_handler.ts            # Cancel + CC-e events
│   │   └── repository.ts               # NFe database operations
│   ├── nfse/
│   │   ├── abrasf_client.ts             # ABRASF SOAP client
│   │   ├── rps_generator.ts             # RPS XML generator
│   │   ├── nfse_authorizer.ts           # NFS-e authorization flow
│   │   ├── municipality_registry.ts     # Pluggable municipality config
│   │   ├── municipalities/
│   │   │   ├── sao_paulo.ts             # SP ABRASF 2.03
│   │   │   ├── rio_de_janeiro.ts        # RJ ABRASF 2.04
│   │   │   ├── belo_horizonte.ts        # BH ABRASF 2.03
│   │   │   └── index.ts                 # Registry + auto-discovery
│   │   ├── danfse_renderer.ts           # DANFSe PDF generation
│   │   └── repository.ts               # NFS-e database operations
│   ├── shared/
│   │   ├── sefaz/
│   │   │   ├── soap_client.ts           # Base SOAP 1.2 client
│   │   │   ├── error_handler.ts         # SEFAZ error classification
│   │   │   ├── retry_policy.ts          # Exponential backoff
│   │   │   └── circuit_breaker.ts       # SEFAZ availability tracking
│   │   └── xml/
│   │       ├── signing.ts               # Base XML signing (XMLDSig)
│   │       └── validation.ts            # XSD validation
│   └── app/api/
│       ├── nfe/
│       │   ├── issue/route.ts
│       │   ├── [id]/cancel/route.ts
│       │   ├── [id]/cce/route.ts
│       │   ├── [id]/status/route.ts
│       │   └── list/route.ts
│       ├── nfse/
│       │   ├── issue/route.ts
│       │   ├── [id]/cancel/route.ts
│       │   ├── [id]/status/route.ts
│       │   └── municipalities/route.ts
│       └── certificates/
│           ├── upload/route.ts
│           └── list/route.ts
├── schemas/
│   ├── nfe_v4.00.xsd
│   ├── nfe_v4.00.tiposBasico.xsd
│   ├── nfe_v4.00_consStatServ.xsd
│   ├── nfe_v4.00_envEvento.xsd
│   └── nfse/
│       ├── abrasf_2.03.xsd
│       └── abrasf_2.04.xsd
├── migrations/
│   ├── XXX_create_nfe_tables.sql
│   └── XXX_create_nfse_tables.sql
└── tests/
    ├── nfe/
    │   ├── xml_generator.test.ts
    │   ├── chave_acesso.test.ts
    │   ├── xml_signer.test.ts
    │   ├── sefaz_client.test.ts
    │   ├── autorizador_router.test.ts
    │   ├── contingency_epec.test.ts
    │   └── mocks/
    │       └── sefaz_responses.py
    ├── nfse/
    │   ├── rps_generator.test.ts
    │   ├── abrasf_client.test.ts
    │   └── municipalities/
    │       ├── sao_paulo.test.ts
    │       ├── rio_de_janeiro.test.ts
    │       └── belo_horizonte.test.ts
    └── shared/
        ├── xml_validation.test.ts
        └── retry_policy.test.ts
```

---

*Generated 2026-07-10 · Batch 3: Compliance & Integrations*
