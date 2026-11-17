GreenLedger - Source and Research Log
Access date: 2026-08-18

This file records authoritative external sources consulted during the data-source verification pass for GreenLedger. Each entry records the exact source, URL, access date, version/year, what was obtained, and how it is used.

1) CORD repository (official project code/metadata)
- URL: https://github.com/clovaai/cord
- Access date: 2026-08-18
- Version / notes: Repository README states CORD v2 release uploaded to Hugging Face on 2022-07-20. The repo itself is the project metadata/code repository, not the dataset archive.
- Information obtained: dataset description, class schema, sample images, split table, and CC BY 4.0 license statement.
- Used in: data/public/cord/METADATA.md and verification of the distinction between the GitHub repo and the actual dataset files.

2) CORD v2 public dataset (official dataset files)
- URL: https://huggingface.co/datasets/naver-clova-ix/cord-v2
- Access date: 2026-08-18
- Version / notes: CORD v2; README states 1,000-receipt dataset with 800 train, 100 dev, 100 test; also states >11,000 receipts in dataset description for full collection. This is the official public dataset source.
- Information obtained: authoritative dataset page and split counts.
- Used in: verifying the actual dataset host and distinguishing it from the repository clone.

3) ICDAR 2019 RRC — SROIE challenge page
- URL: https://rrc.cvc.uab.es/?ch=13&com=downloads
- Access date: 2026-08-18
- Version / notes: SROIE 2019 challenge page; registration required for downloaded files.
- Information obtained: official challenge page, registration requirement, dataset description, and task details. It states that the dataset has 1000 scanned receipt images, with trainval = 600 and test = 400, and that a registration step is required to access downloads.
- Used in: data/public/sroie/METADATA.md

4) FATURA — official paper and public dataset record
- URL: https://arxiv.org/abs/2311.11856 and https://zenodo.org/records/8261508
- Access date: 2026-08-18
- Version / notes: arXiv:2311.11856v1 (20 Nov 2023), article title: "FATURA: A Multi-Layout Invoice Image Dataset for Document Analysis and Understanding". The paper states 10,000 invoices and 50 layouts. The Zenodo record is the public dataset distribution page.
- Information obtained: exact dataset name, original publisher/institutions, size, and public distribution record.
- Used in: data/public/fatura/METADATA.md as a verified source for the public FATURA invoice dataset.

5) GHG Protocol Corporate Standard (official standard PDF)
- URL: https://ghgprotocol.org/sites/default/files/standards/ghg-protocol-revised.pdf
- Access date: 2026-08-18
- Version / notes: "A Corporate Accounting and Reporting Standard" - Revised Edition, with the document content describing the standard and references to the GHG Protocol Initiative.
- Information obtained: exact official corporate standard PDF and the accounting framework for scope definitions and inventory design.
- Used in: GreenLedger source verification and scope/category mapping.

6) GHG Protocol Corporate Value Chain (Scope 3) Standard
- URL: https://ghgprotocol.org/corporate-value-chain-scope-3-standard
- Access date: 2026-08-18
- Version / notes: official current standard page; the page refers to the Corporate Value Chain (Scope 3) Standard and includes 2022 corrections and FAQ resources.
- Information obtained: official definitions for Scope 3 categories and accounting logic; not a numerical emission factor dataset.
- Used in: GreenLedger activity mapping and scope-category documentation.

7) IPCC Emission Factor Database (EFDB)
- URL: https://www.ipcc-nggip.iges.or.jp/EFDB/main.php
- Access date: 2026-08-18
- Version / notes: official EFDB website; page states it is undergoing a renewal and is a searchable repository/library of emission factors and related technical references.
- Information obtained: authoritative source for discovering documented emission factors and the associated technical reference material.
- Used in: emission-factor schema and verification standard for GreenLedger.

8) Central Electricity Authority (CEA), India
- URL: https://cea.nic.in
- Access date: 2026-08-18
- Version / notes: official CEA site; individual CO2 baseline files are publication/year specific. V22.0 and its direct URL are recorded in entry 15; check the CEA archive before later use because annual vintages change.
- Information obtained: official site is the authoritative source, but the exact baseline file/version must still be retrieved manually and recorded.
- Used in: documenting CEA as the required official Indian electricity baseline source.

9) CORD license metadata
- URL: https://github.com/clovaai/cord
- Access date: 2026-08-18
- Version / notes: "This work is licensed under a Creative Commons Attribution 4.0 International License."
- Used in: verifying CORD license.

10) FATURA dataset license and distribution
- URL: https://zenodo.org/records/8261508
- Access date: 2026-08-18
- Version / notes: Zenodo record 8261508; public FATURA dataset. Official record metadata lists CC BY 4.0.
- Information obtained: exact public distribution record, MD5 checksum, file size, and the downloaded archive itself.
- Used in: FATURA verification, local download validation, and metadata documentation.

11) FATURA ZIP download (official Zenodo file endpoint)
- URL: https://zenodo.org/api/records/8261508/files/FATURA.zip/content
- Access date: 2026-08-18
- Version / notes: file name FATURA.zip; size 363,504,027 bytes; MD5 a25c4f9292630f94774e0ca29d121e82; license CC BY 4.0.
- Information obtained: downloaded archive saved to data/public/fatura/FATURA.zip and verified by MD5.
- Used in: local FATURA dataset verification and extracted structure analysis.

11) CEA CO2 Baseline Database V21.0 (official workbook)
- File path: knowledge_base/emission_factors/CO2_Database_V_21.0.xlsx
- URL: https://cea.nic.in
- Access date: 2026-08-18
- Version / notes: Version 21.0; date shown in workbook as 2025-11-01; title indicates Central Electricity Authority: CO2 Baseline Database.
- Information obtained: workbook sheet names and electricity-sector plant generation/emissions tables, including weighted average, operating margin, build margin, and combined margin outputs, plus fuel assumptions and methodology notes.
- Used in: GreenLedger electricity-factor source review and scope-2 accounting interpretation.

12) CEA User Guide for CO2 Baseline Database V21.0
- File path: knowledge_base/emission_factors/User_Guide_V_21.0.pdf
- URL: https://cea.nic.in
- Access date: 2026-08-18
- Version / notes: Version 21.0; November 2025; published by Government of India, Ministry of Power, Central Electricity Authority.
- Information obtained: purpose, database history, calculation methodology, and definitions for interpreting the electricity factors and baseline assumptions.
- Used in: GreenLedger methodology and usage limitations review for electricity factors.

13) GHG Protocol Corporate Standard (Revised Edition)
- File path: knowledge_base/standards/GHG Protocol Corporate Standard Revised (English).pdf
- URL: https://ghgprotocol.org/sites/default/files/standards/ghg-protocol-revised.pdf
- Access date: 2026-08-18
- Version / notes: revised edition presented in the file title; guidance text defines scope 1, scope 2, and scope 3, and explains electricity-related boundary decisions.
- Information obtained: operational boundary definitions, scope distinctions, and general accounting method relevant to GreenLedger’s Scope 1/2/3 structure.
- Used in: GreenLedger accounting model design and scope classification.

14) GHG Protocol Scope 3 Calculation Guidance
- File path: knowledge_base/standards/Scope3_Calculation_Guidance_0[1].pdf
- URL: https://ghgprotocol.org/corporate-value-chain-scope-3-standard
- Access date: 2026-08-18
- Version / notes: Scope 3 Technical Guidance / Corporate Value Chain (Scope 3) Standard material; includes category guidance for purchased goods and services, fuel- and energy-related activities, and upstream/downstream transportation.
- Information obtained: category mapping relevant to purchased electricity, purchased materials, and transport-related activity data and emission factor use.
- Used in: initial GreenLedger scope mapping and activity-data definitions.

---
Verified status summary:
- CORD: verified as public code + official dataset from HF; GitHub repo is not the dataset itself.
- SROIE: official challenge dataset source verified; requires registration/manual access.
- FATURA: verified as an official public invoice dataset from the paper and Zenodo record; downloaded and MD5-verified. Not a carbon dataset.
- CEA V21.0 is retained as historical source. CEA V22.0 (August 2026) is the latest version listed on the official archive as of the 2026-09-24 access date. Its CO2-only weighted-average series is recorded, but is not a verified CO2e factor.
- GHG Protocol: verified as official accounting authority for scope definitions and accounting methodology.
- IPCC EFDB: verified as official emission-factor source.
- CEA: official V22.0 workbook and guide retrieved, hashed, and recorded; the CO2e method/source requirement remains unresolved.

15) CEA CO2 Baseline Database V22.0 (official workbook and user guide)
- Archive URL: https://cea.nic.in/cdm-co2-baseline-database/?lang=en
- Workbook URL: https://cea.nic.in/wp-content/uploads/baseline/2026/09/Baseline_Carbon_Dioxide_Emission_Database_Version_22.0.xlsx
- User guide URL: https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf
- Access date: 2026-09-24
- Version / notes: Version 22.0, August 2026; adds FY2025-26 and revises prior-year results including FY2024-25.
- Local files: knowledge_base/emission_factors/CO2_Database_V_22.0.xlsx and User_Guide_V_22.0.pdf
- SHA-256: workbook F2341EFE03D2FCE4177A4A7090B8A946A5AC5AE32B41D784882D0226F2EB4860; guide 723331B2ADD30754B8794D57DC05126218B3489F9F87CE3E570D5659BDC9D3B0.
- Verified information: Results sheet and guide Appendix C identify the India weighted-average grid CO2 rate; the import-adjusted, RES/captive-inclusive 2025-26 value is 0.675 tCO2/MWh. The source reports CO2, not CO2e.
- Used in: GreenLedger catalogue's CO2-only source-value records. These are explicitly blocked from CO2e calculation pending a GHG-complete factor/method.

16) GHG Protocol Scope 2 Guidance and correction record (official published guidance)
- Landing page: https://ghgprotocol.org/scope-2-guidance?page=1
- Published guidance PDF: https://ghgprotocol.org/sites/default/files/2023-03/Scope%202%20Guidance.pdf
- Corrections PDF: https://ghgprotocol.org/sites/default/files/2023-03/List%20of%20Corrections%20to%20the%20Scope%202%20Guidance.pdf
- Access date: 2026-09-24
- Version / notes: Published 2015 Scope 2 Guidance, with official corrections through April 2025. The landing page reports a 2025-26 public consultation; no final replacement was listed there at access time.
- Local files: knowledge_base/standards/GHG_Protocol_Scope2_Guidance_2015.pdf and GHG_Protocol_Scope2_Guidance_Corrections.pdf.
- SHA-256: guidance B4F17030E5D723D5B9B65ED85592C5449DAFE4F798EB845ED9DB0465893C894A; corrections B7772E0D86764383B41F923BFCACE305D239AC5BAF39AD22FFB55F78BA9DACAD.
- Information obtained: location-based accounting uses grid-average emission factors; market-based factors use qualifying contractual instruments. The guidance treats Scope 2 as GHG emissions and distinguishes grid-average factors from marginal/CDM baseline factors.
- Used in: method separation and to prevent CEA's CO2-only baseline values from being mislabeled as a full CO2e factor.

17) IPCC 2006 Guidelines: LPG stationary combustion defaults and net calorific value
- Stationary combustion chapter (Vol.2 Ch.2): https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Stationary_Combustion.pdf
- Fuel NCV chapter (Vol.2 Ch.1): https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_1_Ch1_Introduction.pdf
- Access date: 2026-09-24
- Version / notes: 2006 IPCC Guidelines; Volume 2 Chapter 2 corrected as of April 2007. Table 2.4 provides commercial/institutional LPG CO2, CH4, and N2O factors on an NCV basis; Table 1.2 provides LPG NCV and lower/upper values.
- Local files and hashes: `knowledge_base/standards/ipcc_sources/README.md`.
- Used in: deriving the conditional global IPCC Tier 1 LPG factor; not an India-specific factor.

18) IPCC AR6 GWP100 values and GHG Protocol GWP amendment
- IPCC AR6 Annex II: https://www.ipcc.ch/report/ar6/wg3/downloads/report/IPCC_AR6_WGIII_Annex-II.pdf
- GHG Protocol amendment: https://ghgprotocol.org/sites/default/files/2022-12/Required%20gases%20and%20GWP%20values_0.pdf
- Access date: 2026-09-24
- Version / notes: IPCC AR6 GWP100 values used for fossil methane from combustion (27.0) and N2O (273). GHG Protocol amendment requires 100-year IPCC values and recommends the most recent assessment report.
- Local files and hashes: `knowledge_base/standards/ipcc_sources/README.md` and `knowledge_base/standards/GHG_Protocol_Required_Gases_and_GWP_Values_Amendment.pdf`.
- Used in: GWP basis for the conditional LPG factor, with the assessment/version preserved in its methodology.
19) Smart Freight Centre India / TCI-IIMB, India Default GHG Emission Values V1.0
- Source page: https://smartfreightcentre.org/news/13311661
- Direct PDF: https://d1c2gz5q23tkk0.cloudfront.net/shrine_store/uploads/networks/3660/communication_news/13311661/08ad10f82dca3ef5ff61a81a137d7274.pdf
- Access date: 2026-11-14
- Version / notes: *India Default GHG Emission Values V1.0 – Complementing GLEC Framework v3.01*. PDF dated May 2025; SFC page published June 30, 2026. Road Transportation / Diesel fuel row reports 2.675 kgCO2e/litre TTW, rounded to three decimals. Independent AR6-based recomputation and the report's printed methane coefficient both round to 2.675. The publication describes values as subject to review/update and has inconsistent nitrogen-species/GWP notation; GreenLedger documents the caveat.
- Local file: `knowledge_base/standards/sfc_india/India_Default_GHG_Emission_Values_V1.0.pdf`
- SHA-256: `8D814B6B3D35D40452EF85ABF560D3EE52DE260875E65DDC76AB8801C4DE7FD6`
- Used in: conditional India Scope 1 road/mobile diesel TTW factor only. It is not applicable to stationary or power-sector combustion, non-road equipment, or freight tonne-km.

## Current factor-verification status (2026-11-14)

- The conditional LPG Tier 1 factor is available only for IPCC 1.A.4.a commercial/institutional stationary combustion under a confirmed Scope 1 boundary, with verified net LPG mass. It is global and not year-specific.
- CEA electricity and diesel entries remain CO2-only. A distinct SFC India road/mobile diesel TTW CO2e factor is available only for confirmed owned/controlled road-vehicle combustion in India. Source-table inputs plus AR6 combustion GWP100 recompute to 2.674884297520661... kgCO2e/L and round to the published 2.675; the report's printed 27.9 methane coefficient also rounds to 2.675. Its source caveat is recorded under `knowledge_base/standards/sfc_india/README.md`.
- Materials, transport, other LPG contexts, and diesel outside the India road/mobile TTW case remain unresolved.

- Run `py -3.12 scripts/validate_factor_catalogue.py` to check catalogue columns and IDs, independent LPG/diesel derivations, applicability metadata, and local source-file hashes.
