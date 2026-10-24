# Research: Optical Metrology (Ellipsometry / Film Thickness) — External Evidence Brief

> **정정 (2026-10-24, 부모 세션):** 이 노트는 서브에이전트의 원본 출력이며 수정하지 않았습니다. 다만 세 곳에서
> 오류가 확인되어 이 정정을 붙입니다. 노트 본문은 서브에이전트 출력 그대로 두고, 정정된 사실은 본문 보고서에
> 반영했습니다. (1) Nature Communications 2025 논문의 저자 소속은
> Park Systems / SK hynix 가 아니라 **전원 삼성전자 반도체연구소**입니다. (2) 그 시스템은 "스테핑 없이 전 웨이퍼"가
> 아니라 **shot/사분면 스테핑 + shot mark 정렬**로 취득합니다. (3) 아래 "no moving stage during field capture" 는
> 벤더 홍보 문구의 요약이며 전계 취득 일반의 사실이 아닙니다. 원문 직접 판독으로 확인했습니다 —
> <https://www.nature.com/articles/s41467-025-63511-1>


Scope: what SE/IMSE and film-thickness data IS, how the industry analyses it, and which standards actually apply. RESEARCH ONLY; no implementation plan.

## Summary

Spectroscopic ellipsometry produces raw spectra (Psi/Delta, or Mueller-matrix elements, vs wavelength and angle of incidence) from which thickness/n/k are extracted by least-squares regression against a physical optical model (Cauchy, Tauc-Lorentz, Sellmeier, B-spline); fit quality is judged by MSE or chi-square *together with* residuals, parameter uncertainties, and correlation matrices — never by the metric alone. Imaging SE (IMSE/IMMSE) turns this into hyperspectral data cubes (e.g., >10M per-pixel spectra per acquisition, 3x3 Mueller matrix, 6.5 um pixels) analyzed increasingly with ML rather than per-pixel physical regression. For factory integration, no single "metrology result schema" standard exists: GEM/SECS-II event reports (S6F11) and EDA traces (E134) carry summary values, SEMI E142 covers substrate *maps*, STDF covers ATE test (not process metrology), and detailed results/spectra move in tool-proprietary formats or CSV exports.

---

## 1. Ellipsometry data model and regression (physics + fit quality)

**Fundamentals (direct evidence, classic + vendor sources; high confidence):**
- rho = rp/rs = tan(Psi)·exp(iDelta); Psi/Delta are measured at each wavelength (and optionally each AOI). Confirmed by Woollam tutorial/FAQ and multiple papers. [Woollam Ellipsometry Tutorial](https://www.jawoollam.com/resources/ellipsometry-tutorial), [Woollam FAQ](https://www.jawoollam.com/resources/ellipsometry-faq)
- Thickness extraction: interference phase delay makes SE sensitive to sub-nm films and up to tens of microns of transparent film; measured quantities are converted to material properties by direct inversion or model-based regression. [Woollam FAQ](https://www.jawoollam.com/resources/ellipsometry-faq), [De Gruyter/spline review (doi:10.1515/aot-2022-0006)](https://doi.org/10.1515/aot-2022-0006) — high confidence.
- Optical dispersion models: Cauchy & classical Lorentz for transparent films; Tauc-Lorentz for absorbing amorphous/semiconductors (VIS-FUV); Drude for metals (Horiba data-analysis page, direct evidence). B-spline: Kramers-Kronig-consistent basis splines avoid guessing oscillator count/lineshape; standard for IR SE. [Horiba data analysis](https://www.horiba.com/twn/scientific/technologies/spectroscopic-ellipsometry/data-analysis/), [JVST B B-spline paper (2020)](https://pubs.aip.org/avs/jvb/article/38/1/014001/591812/Application-of-a-B-spline-model-dielectric) — high confidence. Sellmeier: widely used but NOT confirmed on the Horiba page fetched; medium confidence as "common model" (textbook-level knowledge, e.g., Fujiwara 2007).
- Multiple AOI / azimuth-resolved data increases sensitivity and decorrelates parameters (patents EP3047520B1, US20250076185; classic JOSA multiple-AOI paper). — high confidence.

**Fit quality / when to flag a fit untrustworthy (direct vendor + literature evidence; high confidence):**
- Horiba (chi-square convention): chi2 ~1 is very good for a simple single layer; up to ~10 acceptable for complex samples *if results are physical*. Additional required checks: visual residual comparison, physical plausibility, error bars (large error bars = model problem), correlation matrix (strong correlations = model problem; fix by adding angles, adding R/T data, or fixing parameters), and quick convergence (suggests unique fit). [Horiba](https://www.horiba.com/twn/scientific/technologies/spectroscopic-ellipsometry/data-analysis/)
- Woollam/CompleteEASE uses MSE as its fit metric; low MSE alone does not prove a good model — added complexity lowers MSE without improving reliability; judge with residuals, uncertainties, correlations (CompleteEASE manual + model-selection paper in Appl. Surf. Sci. 2017). [CompleteEASE manual (PDF)](https://physlab.lums.edu.pk/images/f/f4/Ellipsometry_manual.pdf), [Model selection paper](https://www.sciencedirect.com/science/article/pii/S0169433216320207) — high confidence. NOTE: MSE thresholds are instrument- and definition-dependent; no universal cutoff (interpretation, well supported).
- Parameter correlation as a warning sign predates modern tools (Woollam co-authored "sensitivities correlation test", Thin Solid Films 1986). [ScienceDirect](https://www.sciencedirect.com/science/article/pii/0040609086902129)
- NIST: different analysis algorithms can yield different thicknesses from the same ellipsometric data (model dependence is a traceability issue). [NIST thin-film ellipsometry metrology](https://www.nist.gov/publications/thin-film-ellipsometry-metrology) — high confidence.
- Canonical textbooks: Fujiwara, *Spectroscopic Ellipsometry: Principles and Applications* (Wiley 2007); Azzam & Bashara, *Ellipsometry and Polarized Light* (1977); Tompkins & Hilfiker, *SE: Practical Application to Thin Film Characterization* (Momentum 2016); Handbook of Ellipsometry (Springer 2018). [Woollam reference books](https://www.jawoollam.com/resources/reference-books), [Wiley](https://onlinelibrary.wiley.com/doi/book/10.1002/9780470060193)

**FAIR/open data effort (relevant precedent, medium-high confidence):** FAIRmat NFDI `pynxtools-ellips` converts vendor ellipsometry files (currently Woollam VASE/CompleteEASE tabular exports: rows of AOI x wavelength x Psi/Delta, plus separate YAML metadata for what the raw export lacks) into the NXellipsometry NeXus schema — evidence that (a) vendor files are tabular Psi/Delta text exports, and (b) context metadata is NOT carried in the vendor file. [pynxtools-ellips tutorial](https://fairmat-nfdi.github.io/pynxtools-ellips/tutorial/convert_your_first_dataset.html), [Woollam parser](https://github.com/FAIRmat-NFDI/pynxtools-ellips/blob/main/src/pynxtools_ellips/parsers/woollam.py). (NXellipsometry field list itself not verified — fetch of the nxdl failed; see Missing evidence.)

## 2. Film thickness metrology data (uniformity metrics)

- WIW = within-wafer variation across sites of one wafer; WTW = wafer-to-wafer (usually of wafer means); LTL = lot-to-lot (usually of lot means). ASTM F1618 (Standard Practice for Determination of Uniformity of Thin Films on Silicon Wafers) explicitly distinguishes WIW from WTW and LTL. [ASTM F1618-96](https://store.astm.org/f1618-96.html) — high confidence.
- Percent non-uniformity has no single universal formula: 3sigma% = 100 x 3s/mean; range% = 100 x (max-min)/mean, or sometimes 100 x (max-min)/(max+min). "3sigma" is a statistical spread, not literal max-min. Sources: US7239737B2 (documents 3sigma WIW convention), US7928019 (range convention). — high confidence on multiplicity of conventions; the takeaway for a data model: store per-site values and let the formula be a reported-config choice, with sampling plan and edge exclusion documented.
- Per-site reporting: one row per measurement site with wafer ID, site coordinates (origin/orientation documented), value, units, status flag; CSV exports are common but tool-specific, no universal schema. [wafertools wafermap data guide](https://wafertools.github.io/wafermap/guide/data/), EPFL Filmetrics F54 page — medium-high confidence (practitioner sources; the "no universal standard" claim is supported by absence of one).
- SEMI MF1530 covers noncontact wafer flatness/thickness/TTV measurement (substrate thickness, not film stacks). [SEMI store](https://store-dev2.semi.org/en-jp/products/mf153000-semi-mf1530-test-method-for-measuring-flatness-thickness-and-total-thickness-variation-on-silicon-wafers-by-automated-noncontact-scanning)

## 3. Industry standards: what applies vs aspirational

**Applies / relevant (verified against SEMI pages & vendor docs):**
- **GEM / SECS stack — actual delivery channel for metrology summaries.** SEMI E5 (SECS-II message content), E30 (GEM), E37 (HSMS transport). Metrology tools report results via GEM Data Collection: S6F11 event reports (configured reports carrying lot/wafer ID, recipe, measurement result variables; S6F12 ack), S2F23 trace setup + S6F1/S6F2 trace samples for periodic data. Exact CEIDs/VIDs/units are tool-specific. [SEMI Information & Control](https://www.semi.org/en/products-services/standards/information_and_control), [SECS/GEM interface manual (gathertech)](https://secs-docs.gathertech.com.tw/gem200/10-collection-events/) — high confidence.
- **GEM300 family:** E39 object services, E40 process job mgmt, E84 carrier handoff, E87 carrier mgmt, E90 substrate tracking, E94 control job mgmt, E116 equipment performance tracking, E148 time synchronization. [SEMI GEM300 tutorial](https://www.semi.org/en/standards-watch-2021Dec/gem300-tutorial-overview) — high confidence.
- **SEMI E142 Specification for Substrate Mapping (current E142-0225, major revision underway 2026):** defines data items to report/store/transmit map data for wafers/frames/strips/trays — per-unit results/bin values — exchanged via SECS/GEM (E142.2 SECS-II protocol; E142.3 web services). This is THE standard for wafer-map exchange from a metrology tool. [SEMI store E142](https://store-us.semi.org/products/e14200-semi-e142-specification-for-substrate-mapping), [SEMI standards watch 2026](https://www.semi.org/en/standards-watch-2026-apr/major-revision-underway-for-semi-e142), [PEER Group E142](https://www.peergroup.com/definition-of-standard/semi-e142/) — high confidence.
- **SEMI EDA / Interface A:** E120 (Common Equipment Model), E125 (Equipment Self Description — discovery of all collectable parameters/events/exceptions), E128 (XML message structures), E132 (auth), E134 (Data Collection Management — DCPs, Data Collection Reports, Traces at constant rate with triggers), E138 (common components), E164 (EDA Common Metadata, models GEM300 in EDA). EDA is the channel for high-volume trace data, not a results-schema standard. **Correction to the task premise:** E116, E139, E140, E142, E148 are GEM300-side standards, NOT part of the EDA suite per Cimetrix's whitepaper; SEMI's own page lists EDA as E120/E125/E128/E132/E134/E138/E164. [Cimetrix EDA whitepaper (PDF)](https://www.cimetrix.com/hubfs/docs/Whitepapers/Introduction-to-EDA-WhitePaper.pdf), [SEMI EDA page](https://www.semi.org/en/next-gen-semi-eda-standards) — high confidence.
  - SEMI E139 = Recipe and Parameter Management (inactive revision E139-0613 listed); SEMI E140 = Process Job Management (per Cimetrix's GEM300 grouping). Note task brief mislabeled these. [SEMI store E139](https://store-us.semi.org/products/e13900-semi-e139-specification-for-recipe-and-parameter-management-rap)
- **STDF:** binary file format for ATE test data (wafer probe/final test, per-device results + summaries). NOT used for process metrology results (thickness, CD, spectra). [STDF V4 spec](https://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com/stdf-eclipse/Stdf-V4-spec.pdf), [SemiEngineering intro to test data formats](https://semiengineering.com/introduction-to-test-data-formats/) — high confidence.
- **SEMI E183 DOES exist but is NOT a metrology schema:** E183 = Specification for Rich Interactive Test Database (RITdb) — a data container/streaming framework for semiconductor TEST data with provenance metadata (published ~2022). No evidence found of any SEMI standard defining a common *metrology-result* (thickness/Psi-Delta) schema. [SEMI store E183](https://store-us.semi.org/products/e18300-semi-e183-specification-for-rich-interactive-test-database-ritdb), [SEMI standards watch](https://www.semi.org/en/standards-watch-2022-March/newly-published-standard-on-data-sharing-and-streaming) — high confidence on existence/scope; the absence claim ("no metrology-schema standard") is an absence-of-evidence finding, medium-high confidence.
- **Correction:** SEMI E125 is Equipment Self Description (EDA), NOT "self-calibrating thickness measurement equipment". [SEMI store E125](https://store-us.semi.org/products/e12500-semi-e125-specification-for-equipment-self-description-eqsd) — high confidence.
- **How results actually arrive (interpretation from the above, high confidence):** summary values via GEM event reports or EDA trace/DCR; wafer maps via E142; full spectra and detailed fit results via tool software exports — CSV/text (Woollam CompleteEASE "Export to Text File" tabular Psi/Delta; verified in [CompleteEASE 6.70 release notes](https://qd-uki.co.uk/wp-content/uploads/2022-11/CompleteEASE-6.70-Release-Notes.pdf)) or proprietary binaries.

**Vendor-proprietary formats — mostly UNVERIFIABLE from public sources:**
- Woollam: CompleteEASE/VASE tabular text exports (.dat) verified via pynxtools-ellips and pyElli parsers (rows: AOI, wavelength, Psi, Delta; header lines with title/acquisition method). ".dtf" as an extension: NOT verified publicly.
- `.spc`: verified as the Thermo Galactic GRAMS binary spectrum format (used across IR/Raman instruments), NOT confirmed as Semilab-specific — Semilab SEA software output format not publicly documented. [spc-parser](https://github.com/cheminfo/spc-parser)
- `.mlf`, `.tkr` (attributed to KLA/Tencor in the task brief): NOT verified in any public source found. KLA Aleris recipe/output file formats are not publicly documented.

## 4. Analyses that matter for a fab user

1. **SPC on thickness/n/k (Xbar-R for subgroups, I-MR for single wafer means, Nelson & Western Electric run rules, Cpk/Ppk).** Inputs: per-lot/per-wafer summary values + spec limits + subgroup definition. Question: is the process in control and capable? Sources: [NIST/SEMATECH e-Handbook ch.6](https://www.nist.gov/publications/nistsematech-engineering-statistics-handbook-chapter-6-process-or-product-monitoring), [ASTM E2587-24](https://www.astm.org/e2587-24.html), [Western Electric rules (Wikipedia, codified 1956)](https://en.wikipedia.org/wiki/Western_Electric_rules) — high confidence.
2. **Uniformity analysis (WIW/WTW/LTL, wafer maps, radial/zonal statistics, edge exclusion).** Inputs: per-site x/y + value per wafer; lot/wafer grouping. Question: where does deposition vary, and does it meet WIW spec? Sources: ASTM F1618, uniformity patents above — high confidence.
3. **Wafer-map spatial signature analysis (pattern classification: ring, edge, center, scratch, sector; clustering, PCA on features, deep learning; taxonomy by shape/size/location).** Inputs: map grids per wafer over time. Question: which process/equipment fault signature is present, and is it drifting? Sources: [Zhou et al. 2026 review (VLSI Journal)](https://www.sciencedirect.com/science/article/pii/S0167926025002524), [Ezzat et al. 2021 IEEE](https://ieeexplore.ieee.org/document/9366812/), [KAIST variational deep clustering](https://pure.kaist.ac.kr/en/publications/variational-deep-clustering-of-wafer-map-patterns/) — high confidence. Note: these are mostly defect-bin-map methods; applying them to continuous thickness maps is researcher inference (zonal/radial statistics and clustering transfer directly).
4. **Tool matching / chamber matching (paired measurements of same wafers on each tool; offset+scale regression tool = a + b x reference; ANOVA with sample/tool/sample x tool effects; crossed Gauge R&R for repeatability vs tool-to-tool reproducibility).** Inputs: same-wafer measurements across tools, reference values. Question: can tools be used interchangeably, and what correction is needed? Sources: [MIT chamber-matching thesis (R2R + statistics)](https://dspace.mit.edu/entities/publication/7d97eee4-eccd-42c7-a2e1-36960c1cf33d), [NIST overlay calibration strategies](https://www.nist.gov/publications/calibration-strategies-overlay-and-registration-metrology), [SKKU precision matching of optical metrology (recent)](https://pure.skku.edu/en/publications/precision-matching-optimization-of-optical-metrology-and-inspecti/) — high confidence.
5. **Run-to-run APC (EWMA controller on thickness error; lambda tunes responsiveness; handles metrology delay; MIMO EWMA variants; virtual metrology feeding R2R).** Inputs: post-process thickness measurements, recipe knob, delay model. Question: what recipe change hits target next run? Sources: [Susto PhD thesis (2022)](https://automatica.dei.unipd.it/wp-content/uploads/2022/08/SustoGianAntonioPhD_thesis.pdf), [MIMO EWMA with metrology delay (ACS IECR)](https://pubs.acs.org/doi/10.1021/ie1008053) — high confidence.
6. **Fit-quality triage / recipe health (MSE or chi2 trends, parameter error bars, correlation flags, residual structure).** Inputs: per-measurement fit diagnostics. Question: which thickness numbers can be trusted for SPC/APC vs which are model failures? Sources: Horiba/Woollam criteria above — high confidence this is done; medium confidence on standardized thresholds (none exist).
7. **Correlation vs reference metrology (TEM cross-section, XRR (ISO 16413:2020, SI-traceable), AFM/stylus step height on masked steps; report agreement vs combined uncertainty, not %).** Inputs: paired SE vs reference measurements on same/nearby area. Question: is the SE model calibrated/valid for this stack? Sources: [ISO 16413:2020](https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso%3A16413%3Aed-2%3Av1%3Aen), [NIST](https://www.nist.gov/publications/thin-film-ellipsometry-metrology), [DTU LabAdviser](https://labadviser.nanolab.dtu.dk/index.php/Specific_Process_Knowledge/Characterization/Measurement_of_film_thickness_and_optical_constants), [Aalto SE-vs-reflectometry comparison](https://research.aalto.fi/en/publications/comparison-of-thin-film-thickness-measurements-using-ellipsometry/) — high confidence.
8. **Cross-tool / cross-method agreement for identical stacks (SE vs spectroscopic reflectometry, e.g. NanoSpec vs Aleris BBSE: SE wins at ultrathin, reflectometry at thick; good agreement shown 10-2000 nm for SiO2/Al2O3 in a 2026 Aalto study).** Inputs: same-wafer dual-method data. Question: which method per thickness range/material? Sources: same Aalto link, [Onto 10-K (NanoSpec)](https://www.sec.gov/Archives/edgar/data/704532/000095017025026729/onto-20241228.htm) — medium-high confidence.

## 5. Imaging spectroscopic ellipsometry (IMSE) specifics

**Primary source (direct evidence, high confidence):** Park Systems / SK hynix, *Ultra-wide-field imaging Mueller matrix spectroscopic ellipsometry for semiconductor metrology*, Nature Communications (2025): [s41467-025-63511-1](https://www.nature.com/articles/s41467-025-63511-1)
- Hyperspectral cube: >10 million individual intensity spectra per acquisition; reduced 3x3 Mueller matrix per pixel (9 elements; no circular terms due to dual rotating linear polarizers).
- 3200x3200 sCMOS, 6.5 um pixel, 20x20 mm FOV, whole-wafer without stage stepping during acquisition; source 170-2500 nm, monochromator 250-1100 nm (3 nm FWHM); DRAM example: 35 wavelengths, 270-780 nm.
- Analysis: ML (ridge regression) trained on reference metrology (SEM) paired with MM spectra averaged over 15x15-pixel regions; PCA 35->16 features; applied to all >10M pixel spectra; RMSE <1 nm (thickness 0.62/0.49 nm; CD ~0.10 nm; overlay ~0.4 nm).
- Value vs spot SE/SEM: 1987x more metrology data points than SEM, 662x faster throughput per point (0.001 s/point); reveals dense spatial signatures (CVD-nozzle hexagon patterns, concentric CD variation, shot-level overlay) invisible to sparse sampling.
- Key architectural difference from spot SE: output is a per-pixel spectra cube + derived parameter maps, not N site records with N spectra; per-pixel physical-model regression is replaced by trained regression/ML models, so "fit diagnostics" per pixel may not exist — trust signals shift to model training/RMSE and reference correlation. (Inference from the paper's method.)

**Commercial lab-scale IMSE (vendor claims, medium confidence — marketing):** Park Systems/Accurion EP4 (multi-pixel simultaneous, ~1 um lateral resolution, 190-1700 nm; [EP4 page](https://alpha.parksystems.com/en/products/ellipsometers/imaging-spectroscopic-ellipsometry-/ep4), [imaging vs non-imaging comparison PDF](https://www.parksystems.com/content/dam/parksystems/product/ellipsometers/ep4/25-08-18_Comparison_Imaging_Non_Imaging_Ellipsometry.pdf)); Axometrics EllipsoStep (per-pixel Psi/Delta/intensity imaging, 1 um resolution, full-res image <4 s; [page](https://www.axometrics.com/products/polarimeters-ellipsometers/ellipsostep)). Both confirm: no moving stage during field capture, pixel-level Psi/Delta spectra, thickness/n/k maps as outputs.

---

## Concrete data-field inventory (as requested)

**RAW (spectra):**
- Per measurement point (site or pixel): wavelength (nm) or energy grid, Psi, Delta at each (wavelength, AOI); or intensity spectra / Mueller-matrix elements (m11..m33 reduced, or full 4x4 for generalized ellipsometry), depolarization.
- Acquisition axes: angle(s) of incidence, azimuth, spectral range/resolution, spot size or pixel size/FOV, integration time, number of acquisitions averaged.
- Optional raw intensity / calibration baseline (dark, reference sample).

**DERIVED (per layer per point):**
- Thickness (nm) per layer of the stack model; optical constants n, k (or epsilon1/epsilon2) vs wavelength; composition/doping/stress where supported (KLA Aleris claims thickness, RI, stress, composition).
- Fit diagnostics: MSE (Woollam convention) or chi-square (Horiba convention), residual arrays, parameter error bars/confidence intervals, correlation matrix flags, convergence info.
- For IMSE/ML recipes: predicted parameter + model RMSE vs reference; per-pixel quality flags may be absent.

**CONTEXT:**
- lot_id, wafer_id (+ slot), substrate ID, recipe/model name + revision (the optical stack model IS part of the result — same spectra can yield different thickness under different models; NIST), tool ID + software version, site/pixel coordinates (x,y with origin/orientation convention + edge exclusion), timestamp (E148-synchronized in GEM300 fabs), layer/stack definition, operator, calibration state, AOI used, measurement status flags (OK/invalid/repeat).
- Delivery context: GEM CEID/RPTID/VID mapping if via SECS, E142 map structure if a map, EDA DCP/trace ID if via Interface A.

## Contradictions

- **EDA suite membership:** SEMI's public pages and Cimetrix list EDA as E120/E125/E128/E132/E134/E138/E164; the task brief's inclusion of E116/E139/E140/E142/E148 in "EDA" conflicts with Cimetrix's whitepaper, which classifies those as GEM300 standards. Both cannot be right; the Cimetrix/SEMI grouping is better sourced.
- **Fit metric convention:** Woollam ecosystem uses MSE; Horiba uses chi-square with ~1 (simple) to ~10 (complex) guidance. No cross-vendor comparable threshold exists — do not hardcode a numeric cutoff.
- **Uniformity formula:** 3sigma% vs range% conventions coexist in patents/practice with no single authority; ASTM F1618 defines the practice but multiple formulas remain in use.

## Missing evidence / unverifiables

- **NXellipsometry exact field list**: repo fetch failed; only verified that it exists and parses Woollam VASE exports with supplemental YAML metadata.
- **`.dtf`, `.mlf`, `.tkr` extensions**: no public documentation found tying these to Woollam/KLA products; treat as unverifiable vendor-proprietary. `.spc` is a Thermo Galactic GRAMS binary format, not confirmed Semilab-specific.
- **SEMI E183-as-metrology-schema**: E183 (RITdb) is test-data scoped; NO SEMI standard for a common *process-metrology result schema* was found (absence of evidence, searched directly).
- Paywalled standards' full texts (E5/E30/E142/E125/E134 etc.) not read — scope statements from SEMI store/vendor summaries only.
- KLA Aleris / Onto in-line IMSE output artifacts (data volumes, map formats) beyond the Nature Comm paper: not publicly documented.
- Whether fabs deliver ellipsometry *spectra* via EDA trace in practice: plausible (trace mechanism exists) but no concrete fab deployment source found.

## Sources kept (primary/authoritative)

- Nature Comm 2025 IMMSE (Park/SK hynix) — best single primary source on IMSE data model & volumes
- Horiba SE data-analysis page — vendor fit-quality criteria (chi2, correlation, error bars)
- Woollam FAQ/Tutorial/CompleteEASE manual — rho definition, MSE, export formats
- Cimetrix EDA whitepaper + SEMI EDA/GEM300 pages — authoritative standard scope & suite membership
- SEMI E142 store page + SEMI standards-watch + PEER Group — substrate mapping standard
- SEMI E183 store page + standards-watch — RITdb scope (test, not metrology)
- STDF V4 spec PDF + SemiEngineering — STDF scope (ATE only)
- ASTM F1618, ASTM E2587-24, NIST/SEMATECH e-Handbook ch.6 — uniformity & SPC practices
- ISO 16413:2020, NIST thin-film ellipsometry — reference correlation & model dependence
- JVST B B-spline (2020), aot-2022-0006 spline review — dispersion model literature
- Fujiwara (Wiley 2007), Azzam & Bashara (1977), Tompkins & Hilfiker (2016) — textbooks
- MIT chamber-matching thesis, NIST overlay calibration, SKKU precision matching — tool matching
- Susto thesis + ACS MIMO EWMA — R2R APC
- Zhou 2026 wafer-map ML review, Ezzat 2021, KAIST VAE clustering — spatial signature analysis
- pynxtools-ellips / pyElli — vendor export structure evidence + FAIR precedent

Rejected/deprioritized: patents.justia US7928019 (kept only for range-formula convention), sibranchwafer.com & jeez-semicon.com (SEO blogs), djvu.online Azzam scan (pirated copy; cite publisher instead), odot.org stray PDF (irrelevant mis-hit), gathertech SECS manual (kept only for S6F11/S6F12 message-level detail, secondary).

## Next steps (only if needed)

- Read actual NXellipsometry nxdl (github.com/FAIRmat-NFDI/nexus_definitions, applications/NXellipsometry.nxdl.xml) for a field-level open-schema precedent.
- Obtain SEMI E142-0225 text (paid) before designing any wafer-map interchange.
- Ask the tool vendors directly for output-format specs (.dtf/.mlf/.tkr claims are unverifiable publicly).
