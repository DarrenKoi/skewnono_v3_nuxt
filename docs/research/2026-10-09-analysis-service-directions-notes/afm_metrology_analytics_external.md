# Inline / automated AFM metrology analytics in HVM — external evidence (as of 2026-10)

Reading guide for the report writer:

- Evidence level is tagged on every finding. **[read]** = I opened the page or document and read it. **[snippet]** = the claim comes from a search-result summary of that page; the page itself was not opened, so wording and numbers should be treated as unverified.
- **[vendor]** = vendor marketing or application note, not peer reviewed. **[peer]** = journal or conference paper. **[patent]** = patent text.
- Anything I know from background but could not source in this session is placed under **Gaps**, labelled "unverified background", never under Cited Findings.
- Coverage is uneven. Strongest: tip wear and tip characterisation (NIST), hybrid-bonding AFM (Bruker AN5001, Nova/IBM 2026), Park NX-Wafer and Bruker InSight AFP feature lists, Gwyddion file-format support. Weakest: throughput and utilisation analytics, tool-to-tool matching practice, IRDS, SEMI standards, Hitachi and Oxford/Asylum, MountainsSPIP. Those are stated as gaps, not filled in.

## 1. Applications: which inline AFM measurements matter in DRAM / 3D NAND / logic, and which are growing

### Takeaway

Inline AFM is sold and used for four families of measurement: CMP planarity (dishing, erosion, edge-over-erosion, long-range topography), etch or recess depth and step height, sub-nanometre surface roughness, and sidewall or CD profiling. The clearest growth driver in 2024 to 2026 sources is hybrid bonding, where Cu pad recess of a few nanometres and dielectric roughness of 0.1 to 0.2 nm Rq must be controlled and AFM is the reference that optical methods are trained against.

### Cited Findings

Hybrid bonding (fastest-growing use in the sources found):

- Bruker application note AN5001 (Sean Hand, Peter De Wolf; 2025) lists the AFM measurements for hybrid bonding as Cu pad recess from cross-section profiles through pads, dielectric roughness Rq, Cu pad roughness, nanoscale defects (pits on Cu, protrusions on dielectric), millimetre-scale long-range topography, and edge roll-off (ERO) and bevel profile. **[read][vendor]** — [Bruker AN5001](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/resource-library/an-5001-surface-metrology-for-hybrid-bonding-in-advanced-semiconductor-packaging.html)
- Numeric targets in the same note: dielectric Rq 0.1 to 0.2 nm; Cu pad recess about 1 to 5 nm for common pad sizes; long-range topography reduced from 25 nm to 15 nm after a CMP adjustment; topography at 100 µm and above must stay in specification; ERO measured at 8 sites at 45° separation with more than 45 wafers per hour; bevel profile length 10 to 25 mm at up to 25 mm/s. **[read][vendor]** — [Bruker AN5001](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/resource-library/an-5001-surface-metrology-for-hybrid-bonding-in-advanced-semiconductor-packaging.html)
- A 2026 SPIE Advanced Lithography + Patterning paper (Timoney et al., IBM Research and Nova) monitors Cu recess inline with vertical travelling scatterometry plus machine learning; the ML model is trained on AFM data, so AFM is the ground truth. It states that even sub-angstrom deviations can affect dielectric bonding or Cu-Cu interface formation. **[snippet][peer, vendor-hosted]** — [Nova-hosted SPIE 2026 paper 13981-16](https://www.novami.com/wp-content/uploads/2026/04/13981-16-timoney-spie-alp-2026-vts-ml-cu-recess-final.pdf)
- IBM describes AFM as providing Cu pad recess relative to the dielectric top surface and top-surface roughness with sub-nanometre precision for hybrid-bonding interface optimisation. **[snippet][peer]** — [IBM Research, AFM-assisted hybrid bonding interface optimization](https://researcher.ibm.com/publications/afm-assisted-hybrid-bonding-interface-optimization)
- Onto Innovation positions OCD as the high-throughput inline Cu-recess method and advertises "strong correlation to AFM results", again placing AFM as the reference. **[snippet][vendor]** — [Onto Innovation, in-line process control for hybrid bonding](https://ontoinnovation.com/resources/enabling-in-line-process-control-for-hybrid-bonding-applications/)
- A 2024 Bruker webinar on automated AFM for inline hybrid-bonding metrology lists bond-pad metrology, large-area topography for wafer-to-wafer bonding and bevel-edge measurement as the topics. **[snippet][vendor]** — [Bruker webinar 2024](https://www.bruker.com/en/news-and-events/webinars/2024/automated-afm-for-inline-hybrid-bonding-metrology-in-the-semiconductor-industry.html)
- A conference paper evaluated automated inline AFM for CMP control including Cu pad CMP in wafer-to-wafer hybrid bonding, citing non-destructive measurement, sub-nanometre accuracy and long-term reliability, and lists a high-density carbon tip among its keywords. **[snippet][peer]** — [VDE proceedings, In-line Atomic Resolution Local Nanotopography Variation Metrology for CMP Process](https://www.vde-verlag.de/proceedings-en/454462012.html)

CMP planarity:

- Park NX-Wafer brochure (2023): CMP profiling up to 50 mm with a long-range travelling (sliding) stage; measures local and global planarity "including dishing, erosion, and edge-over-erosion (EOE)"; shows die-level profiling over a 25 mm line with heights from about +80 to −120 nm. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)
- Bruker InSight AFP page: dishing and erosion monitored on submicron features for CMP APC; Large Area Scanning from tens of nm to 300 mm; 3D die mapping of a full 33 mm × 26 mm flash field in 24 hours at 1 µm × 1 µm pixels with automatic hot-spot detection and rescan. **[read][vendor]** — [Bruker InSight AFP](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-afp.html)

Depth, step height, 3D NAND:

- Park brochure example for 3D NAND: staircase line profile with a cursor reading ΔX 0.845 µm, ΔY 0.100 µm labelled "ΔY = Step height" on a 20 µm scan with 6 µm peak-to-valley. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)
- Bruker InSight AFP: "Etch APC (depth)" with an adaptive DTMode, move-acquire-measure time under 10 s, and etch process development for NAND and power devices. **[read][vendor]** — [Bruker InSight AFP](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-afp.html)
- Older but still relevant for DRAM: a 2004 SPIE study on polysilicon recess etch in DRAM deep-trench arrays says AFM had been the standard post-etch depth check but is limited as trench widths shrink (restricted bottom travel); recess depths were roughly 150 to 300 nm. **[snippet][peer]** — [SPIE 5375, scatterometry for depth and linewidth of DRAM recess](https://proceedings.spiedigitallibrary.org/conference-proceedings-of-spie/5375/0000/Spectroscopic-ellipsometry-based-scatterometry-for-depth-and-linewidth-measurements-of/10.1117/12.535646.full)

Roughness:

- Park brochure: noise floor "less than 1 Å rms throughout the entire wafer area"; SOI wafer example line profile within ±0.4 nm over 1 µm; Z scanner noise floor < 0.05 nm in the specification table. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)

Sidewall, EUV resist, defects:

- Bruker InSight AFP: CDMode for sidewall and sidewall-roughness characterisation "that reduces cross-sectioning"; EUV APC through top line roughness monitoring, with the statement that a resist with 9% lower top line roughness on average develops significantly fewer line-break defects; pico-Newton force control (TrueSense) for non-destructive resist profiling. **[read][vendor]** — [Bruker InSight AFP](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-afp.html)
- Park brochure: photoresist pattern example where about 8 nm height shrinkage from e-beam damage was measured by AFM (a use of AFM to quantify CD-SEM-induced resist shrink). **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)
- Park brochure: automatic defect review (ADR) for 300 mm bare wafers, with defect-map transfer, coordinate remapping using wafer edge and notch, survey scan then zoom-in scan, and automated analysis of imaged defect types. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)
- Nearfield Instruments says its QUADRA system targets memory (VNAND, DRAM, HBM) and logic, including high-aspect-ratio structures and hybrid bonding. **[snippet][vendor press release]** — [Nearfield Instruments Lightning Mode release, 2024](https://www.generation-nt.com/communiques-presse/nearfield-instruments-eur-quadra-in-line-semiconductor-metrology-2048804)

### Inferences

- The questions engineers ask of the data follow from the applications: is recess or dishing inside a nanometre-scale window at every site, is roughness below a sub-nanometre limit, does long-range topography exceed a limit at ≥100 µm wavelengths, and is the edge different from the centre.
- Hybrid bonding raises the value of two things an analytics layer can provide from summary numbers: per-pad or per-site distributions (not just a wafer mean) and separation of real process shift from tip or tool drift, because the specification window (1 to 5 nm recess, 0.1 to 0.2 nm Rq) is close to tip-induced bias.
- Depth measurements are bounded by tip geometry (see section 2), so "depth versus tip age" is a natural cross-check for recess and trench applications.

### Gaps

- No source found that ranks AFM applications by volume specifically inside DRAM or 3D NAND fabs; the growth claim for hybrid bonding rests on the density of 2024 to 2026 vendor and conference material, not on a market figure.
- IRDS Metrology chapter was not retrieved; no IRDS statement is cited here.
- Photomask repair, STI or gate recess, and wafer-edge bow were not covered by any source I opened.
- SEMI standards on AFM or step height were not retrieved.

## 2. Tip management: wear, characterisation, life prediction, bias, exchange criteria, group monitoring

### Takeaway

Tip width or shape is the largest accuracy term in CD-type AFM and it changes continuously with use, so the standard practice is to qualify the tip on a characteriser at fixed intervals and track wear against a usage counter. The best-documented wear metric is nanometres of tip-width loss per millimetre of sidewall travel (or per site), with a fast initial phase followed by a slower steady phase.

### Cited Findings

Wear rates and their shape (Orji, Dixson, Lopez, Irmer, "Wear comparison of critical dimension-atomic force microscopy tips", J. Micro/Nanolith. MEMS MOEMS 19(1) 014004, 2020) **[read][peer]** — [PMC7724968](https://pmc.ncbi.nlm.nih.gov/articles/PMC7724968):

- Wear in nm per mm of sidewall travel. EBD diamond-like-carbon tips: initial 0.99, 1.66, 1.87; extended 0.15, 0.30, 0.40; overall 0.20, 0.39, 0.44. Silicon tips: 2.55 and 3.5 initial, then catastrophic failure.
- EBD tips show a bilinear pattern: faster at first, slowing after about 2 mm of sidewall travel (authors' hypothesis: blunting lowers contact stress).
- Longest tip life in the study: 3188 sites at 0.0032 nm per site; another tip ran 13.04 mm of sidewall travel (2139 sites). A prior silicon-tip study is quoted at 0.0073 nm per site.
- The paper's own summary numbers are inconsistent (abstract: "more than 17 times" lower wear; conclusion: "approximately 8 to 17 times lower").
- Monitoring schedule used: tip qualification every 10 primary-site measurements; two monitor sites remeasured every 500 images; three primary sites rotated to limit substrate wear; monitor-site differences stayed below 0.5 nm.
- Tip shape parameters extracted (tangent-slope and modified-erosion method after Dahlen et al.): tip width, vertical edge height (VEH), effective tip length, tip profile. Characteriser samples: IVPS and IFSR (Team Nanotec); width traceability via NIST SCCDRM and a VLSI Standards NanoCD45; tip-width uncertainty 0.95 nm (k=1).
- Bias mechanisms stated: untracked tip-width change appears as apparent feature-size change; a 10 nm VEH means the bottom 10 nm of a feature is not captured; effective tip length limits the deepest measurable trench; about 10 nm of wear can remove the flare and prevent re-entrant imaging; wear of the calibration site itself inflates the computed tip width.
- Linewidth results alone did not reveal wear: mean linewidths stayed 114.0 to 114.9 nm with standard deviation 0.41 to 0.61 nm across tips with different wear rates. The authors recommend reporting wear per mm of sidewall travel, not total scan length, which underestimates wear for CD tips.

Tip-width calibration and standards (NIST):

- NIST treats the tip effect in CD-AFM as an offset subtracted from apparent width, and calibration uncertainty of tip width is a major uncertainty source. Commercial tip-characteriser samples can damage tips and give at least 5 nm uncertainty; NIST single-crystal CD reference materials calibrate tip width to about 1 nm standard uncertainty (k=1). **[snippet][peer]** — [NIST, Comparison and uncertainties of standards for CD-AFM tip width calibration](https://www.nist.gov/publications/comparison-and-uncertainties-standards-cd-afm-microscope-tip-width-calibration)
- Two independent tip-width reference calibrations on three CD-AFM instruments agreed within uncertainty and were stable for more than 10 years, with episodes of sample damage or cleaning (Dixson and Orji, JM3 16(2)). **[snippet][peer]** — [NIST publication page](https://www.nist.gov/node/1228331)
- Dixson, Orji, Goldband (JM3 15(1) 014003, 2016): CD-AFM tips range from 15 nm to 850 nm in width; dither slope about 3 nm/V for large tips versus 4.0 to 4.5 nm/V for small tips; no residual bias results provided tip calibration and sample measurement are done under the same conditions; an IVPS feature of about 800 nm is "extremely robust against damage during scanning". **[read][peer]** — [PMC4832421](https://pmc.ncbi.nlm.nih.gov/articles/PMC4832421)

Blind tip reconstruction (BTR):

- Villarrubia's 1997 BTR estimates tip shape from the image alone using mathematical morphology; it works on noise-free images and is noise-sensitive. Later work adds regularisation and an end-to-end differentiable version (Scientific Reports, 2023). **[snippet][peer]** — [Regularized BTR, arXiv 1105.1472](https://arxiv.org/pdf/1105.1472); [End-to-end differentiable BTR, PMC9813222](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9813222/)
- Flater et al. (2014): BTR uptake is hindered by uncertainty over tip matrix size and threshold, which strongly affect the result. **[snippet][peer]** — [Flater et al., Ultramicroscopy preprint](https://cdm.me.wisc.edu/pub/blindTipEstimationUltramicroscopy.pdf)
- BTR used to track wear: Liu et al. (ACS Nano 2010) measured volume loss over a wear test with intermittent BTR and found agreement with TEM. Vorselen et al. (2016) tracked tip radius by fitting single peaks in images, in agreement with BTR, and showed broadening is gradual. **[snippet][peer]** — [Liu et al. ACS Nano 2010](https://alliance.seas.upenn.edu/~carpickg/dynamic/wordpress/wp-content/uploads/2014/01/Liu_ACSNano_2010.pdf); [Vorselen et al., Sci. Rep. 2016](https://www.nature.com/articles/srep36972)
- On Gaussian random rough surfaces, BTR tip-radius accuracy depends on the ratio of actual tip radius to the rms radius of curvature of the surface; the ratio must exceed 3/2 for an accurate estimate. **[snippet][peer]** — [Springer, s11801-007-7017-z](https://link.springer.com/article/10.1007/s11801-007-7017-z)

Tip wear and roughness or height bias:

- NPL: measured rms roughness is only slowly reduced as tip radius increases, while the profile is distorted; the larger concern is bias in mean height, which biases step height when film and substrate roughness differ. Non-Gaussian height distributions are more sensitive to tip radius. Tip radius grows through contamination build-up, breakage or sliding wear. **[snippet][peer]** — [NPL eprint 5751](https://eprintspublications.npl.co.uk/5751/); [NPL eprint 6321](https://eprintspublications.npl.co.uk/6321/)
- Park (vendor): as tip radius increases, measured roughness decreases. **[snippet][vendor]** — [Park, Surface Roughness Measurement of Media and Substrate](https://parksystems.com/applications/afm-exclusive/4018-surface-roughness-measurement-of-media-and-substrate)
- Park brochure reference-sample style evidence: Rq 0.669, 0.674, 0.665, 0.642 nm at the 1st, 5000th, 10000th and 15000th repeat (average 0.662 nm, 1σ 0.011 nm or 1.720%); Ra 0.527 to 0.508 nm (average 0.524, 1σ 1.835%), offered as proof that True Non-Contact mode preserves the tip. Claim of "10x - 20x longer tip lifetime than any other AFM". **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)

Exchange automation and vendor tip management:

- Park NX-Wafer: automatic tip exchanger locates tips by pattern recognition, uses a magnetic mechanism, advertises a 99.9% success rate, replaces the probe when a threshold is exceeded, and holds up to 24 pre-mounted probes (12 per cassette). The threshold definition is not published. **[snippet][vendor]** — [Park NX-Wafer product page](https://www.parksystems.com/products/industrial/park-wafer/applications)
- Bruker InSight 300: TipX probe automation, probes loaded and checked against recipe requirements, automatic probe-shape qualification, vacuum-held probes, 4 cassettes of 25 tips (100 total), recipe-controlled tip management and resource tracking. **[snippet][vendor]** — [Bruker InSight 300](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-300.html)
- Fraunhofer ENAS describes the Bruker InSight CAP as a fully automatic AFM for SPC and batch analysis with an integrated tip management and qualification system that monitors tip condition during high-volume measurement. **[snippet][institute]** — [Fraunhofer ENAS, Atomic Force Microscopy](https://www.enas.fraunhofer.de/en/Business_Units/Cross-Functional_Topics/Fab-Management/InlineMetrology_and_Data/atomic-force-microscopy.html)
- Bruker InSight AFP advertises "2 pm long-term probe-to-probe repeatability and reproducibility" for CMP APC and a "Longest Tip Life" heading with no number. **[read][vendor]** — [Bruker InSight AFP](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-afp.html)

### Inferences

- Data needed to track tip life, derived from the NIST method: per-tip identity and type or material; cumulative sites or images; cumulative scan length and, for sidewall-contact modes, sidewall travel length; periodic qualifier results (width, VEH, effective length, or radius); and results on a fixed monitor site. Wear rate is then the slope of qualifier width against the usage counter, fitted as two segments (run-in and steady state).
- A usable tip-health indicator that needs no raw data: trend of a reference or monitor-site result (roughness Rq, or a known step or width) against tip usage count, per tip. Park's own brochure uses exactly this shape of evidence (Rq against repeat number).
- Because product linewidth statistics did not reveal wear in the NIST study, product results alone are a weak tip-wear detector; a dedicated qualifier or monitor-site series is required.
- Probe-to-probe offset is a distinct quantity from within-tip wear. A step in a result series aligned with a tip-exchange event indicates tip-to-tip offset; a slope inside one tip's life indicates wear.
- Direction of bias for implementation rules: blunter tip gives lower Rq, shallower apparent depth in narrow trenches, wider apparent lines and narrower apparent trenches.

### Gaps

- No published fab criteria for tip exchange (threshold values on width, radius, scan count) were found; vendors state that a threshold exists without defining it.
- No source describing how a fab monitors tip health across a tool group, nor any tip-life prediction model beyond the linear and bilinear wear-rate fits above.
- No quantitative study found of how tip wear over a series biases Ra or Rq when the tip is re-estimated by BTR.
- Wear data found are for CD-AFM flared tips in a CD mode; equivalent published numbers for non-contact or tapping conical tips on CMP or roughness recipes were not found (only Park's vendor repeat test).

## 3. Measurement quality and tool health: repeatability, TMU, reference standards, drift, artefacts, matching

### Takeaway

The established accuracy framework for comparing a tool against a reference is total measurement uncertainty (TMU) from Mandel regression, which originated with CD-AFM as the reference system; long-term stability is demonstrated by repeated measurement of traceable reference structures over years. Vendor specifications give the tool-health quantities worth monitoring (noise floor, out-of-plane motion, long-term stability) but published fab practice for AFM tool-to-tool matching is thin.

### Cited Findings

- TMU method (Banke and Archie, "Characteristics of Accuracy for CD Metrology", Proc. SPIE 3677, 1999, as described in the IBM patent family): the measurement system under test is regressed against a reference measurement system; the patents use CD-AFM as reference and CD-SEM as the system under test. Mandel regression (1964, revised 1984) is used because ordinary least squares assumes an error-free x. The Mandel total scatter about the fit is the sum of the squared tool-under-test component and the squared reference-system component, so TMU is obtained by removing the reference uncertainty from the net residual. **[snippet][patent]** — [US7352478B2](https://patents.google.com/patent/US7352478); [US7286247](https://patents.google.com/patent/US7286247)
- A SPIE paper on CD-AFM calibration used linewidth fingerprinting with Mandel regression to assess correlation to NIST-derived calibration data and reported combined expanded uncertainty below 2 nm at k=3. **[snippet][peer]** — [SPIE profile listing, James Robert](https://biomedicaloptics.spiedigitallibrary.org/profile/James.Robert-79632)
- Long-term stability by reference standards: two independent tip-width references across three CD-AFMs agreed within uncertainty for more than 10 years. **[snippet][peer]** — [NIST publication page](https://www.nist.gov/node/1228331)
- Environmental control used in NIST wear and calibration work: 20 °C ± 0.25 °C, 40% ± 5% relative humidity. **[read][peer]** — [PMC7724968](https://pmc.ncbi.nlm.nih.gov/articles/PMC7724968)
- Bruker InSight AFP tool-health specifications: 0.3 nm long-term stability described as NIST-traceable and measured over one year; less than 1 nm out-of-plane motion over a 105 µm scan range; capacitive gauges and air-bearing positioning; less than ±250 nm raw image placement accuracy with 100× registration optics. **[read][vendor]** — [Bruker InSight AFP](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-afp.html)
- Park NX-Wafer specifications: XY flexure scanner with closed-loop control, 100 × 100 µm (large), 50 × 50 µm, 10 × 10 µm modes; Z scanner range 15 µm (large) or 2 µm (small); Z resolution 0.016 nm or 0.002 nm; Z noise floor < 0.05 nm; motorised stage repeatability < 1 µm; Cognex pattern recognition with 1/4 pixel align resolution; operating temperature 18 to 24 °C, humidity 30 to 60%, floor vibration VC-D (6 µm/s), acoustic noise below 65 dB. It also advertises "superior tool-to-tool matching" and "minimized tip-to-tip variation" without numbers. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)
- Park claims that, with its decoupled scanner and sliding stage, "there is no need for complex background subtraction or past processing after each measurement in general" for long-range CMP profiles. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)
- Bruker AN5001 reports ERO repeatability as 3σ precision for two measurement regions R1 and R2 against a reference region (values only in a figure). **[read][vendor]** — [Bruker AN5001](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/resource-library/an-5001-surface-metrology-for-hybrid-bonding-in-advanced-semiconductor-packaging.html)
- Scan artefact categories named in the recent ML literature: scan-line distortions, streaks, pits, sample-induced anomalies; tip contamination and "not tracking" appear as defect classes. **[snippet][preprint]** — [Artifact Removal and Image Restoration in AFM, arXiv 2602.04051](https://arxiv.org/html/2602.04051v1); [AFM defect classification with LLM decision support](https://jrrade-afm-defect-detection-llm-page.static.hf.space/)
- Roughness values are bandwidth-dependent: the lower spatial-frequency limit is the inverse scan length and the upper limit is Nyquist from the sampling interval; Rq from instruments with different bandwidths is not directly comparable, and comparison should use PSDs over overlapping frequency ranges. **[snippet][peer]** — [SPIE 7656, comparison of roughness by stylus, AFM and optical](https://spiedigitallibrary.org/conference-proceedings-of-spie/7656/76562D/Comparison-of-optical-surface-roughness-measured-by-stylus-profiler-AFM/10.1117/12.863268.full)

### Inferences

- A tool-health service implementable from stored summary results: per-tool control charts on a reference-wafer or monitor-site parameter (step height, Rq), with tip-exchange events overlaid so tool drift, tip wear and tip-to-tip offset can be separated.
- Tool-to-tool matching can be expressed with the same Mandel/TMU machinery by treating one tool (or the group mean) as the reference, provided the same wafers and sites are measured on both tools; slope and offset from the regression are the matching metrics and the residual is the non-matchable part.
- Scan size, pixel count, scan mode and tip type must be stored with every roughness value, otherwise Rq values from different recipes are not comparable; this is a metadata-completeness check an application can enforce.
- Levelling choice is a hidden parameter for step height and dishing. Vendor text treats flat, background-free profiles as a selling point, which implies results from recipes with different flattening orders should not be trended together without that field recorded.

### Gaps

- No published procedure found for AFM group matching in a fab (matching budget, frequency, artefacts used).
- No AFM-specific gauge R&R or precision-to-tolerance thresholds were found; SEMI documents were not retrieved.
- Scanner calibration details (Z linearity, XY orthogonality, thermal drift rates) and their monitoring were not found beyond the vendor specification lines above.
- Effects of levelling or flattening order on step-height and roughness results were not sourced quantitatively.
- Artefact types such as tip doubling, parachuting and feedback oscillation are named in the assignment but I found no source that defines detection criteria for them.

## 4. Result analytics: SPC, wafer maps, pattern dependence, overlays, PSD, correlation and reference-metrology role

### Takeaway

The well-defined analytics are (a) dishing and erosion from a line profile referenced to the field region, with known pattern-width and pattern-density dependence, (b) ISO areal roughness parameters and PSD with explicit bandwidth, and (c) regression of another metrology against AFM as reference, which is how AFM is used to validate OCD and now to train ML scatterometry models.

### Cited Findings

CMP definitions and pattern dependence:

- Dishing is the difference in metal thickness between the edge of a line and its centre; erosion is the difference in oxide thickness above a metal line (typically in an array) relative to an adjacent unpatterned region. The field region next to the array defines the reference point for erosion. Line scans from an AFM or profiler across test-chip patterns are the standard data. **[snippet][patent]** — [US 8001516, Characterization and reduction of variation for integrated circuits](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8001516)
- Typical trends: dishing increases with trench (line) width; erosion increases with pattern density. Dishing is not determined by line width alone; isolated and array lines of the same width dish differently. Interaction distance for Cu is on the order of 50 to 100 µm versus 3 to 5 mm for conventional oxide polish. **[snippet][peer]** — [MIT (Boning group), Overview of Methods for Characterization of Pattern Dependencies in Copper CMP](https://boning.mit.edu/wp-content/uploads/2022/11/Overview-of-Methods-for-Characterization-of-Pattern-De­pendencies-in-Copper-CMP.pdf)
- Long-range AFM profiling (30 mm sliding stage) has shown strong centre-to-edge differences in dishing and erosion; process window narrows as film stacks shrink. **[snippet][peer]** — [VDE proceedings, In-line Atomic Resolution Local Nanotopography Variation Metrology for CMP Process](https://www.vde-verlag.de/proceedings-en/454462012.html)
- Cu recess depths of 5 to 25 nm after barrier removal in a two-step CMP are reported in older hybrid-bonding process work. **[snippet][presentation]** — [NCCAVS user group presentation, 2023](https://nccavs-usergroups.avs.org/wp-content/uploads/2023/09/JointUG923-5-BasimGB.pdf)

Comparison and overlay practice shown by vendors:

- Bruker AN5001 compares pad topography across three CMP skews side by side on a common vertical axis, compares cross-section profiles for pad-depth change, combines multiple radial profiles into a wafer topography heat map, repeats the same recipe on a 26 × 5 mm region before and after a CMP change, and states results support SPC monitoring. **[read][vendor]** — [Bruker AN5001](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/resource-library/an-5001-surface-metrology-for-hybrid-bonding-in-advanced-semiconductor-packaging.html)
- Park's automated analysis output for a line/space profile lists Height, Width, Interval, Pitch, Angle (L), Angle (R) (example: 175 nm, 560 nm, 440 nm, 1000 nm, 54.5°, 54.5°); image-level outputs shown are peak-to-valley and RMS roughness, and cursor ΔX/ΔY pairs. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)

Roughness and PSD:

- ISO 25178-2 defines areal parameters; height parameters depend only on the height distribution; Sq is the root mean square height over the sampling area; Ssk and Sku are the third and fourth moments normalised by Sq³ and Sq⁴; hybrid parameters such as Sdq combine height and spacing. Current edition is ISO 25178-2:2021. **[snippet][standard preview / encyclopedia]** — [ISO 25178-2:2021 preview (ANSI)](https://webstore.ansi.org/preview-pages/ISO/preview_ISO+25178-2-2021.pdf); [Wikipedia, ISO 25178](https://en.wikipedia.org/wiki/ISO_25178)
- PSD stitching across scan sizes requires partially overlapping spatial-frequency ranges; one wafer-type study combined 2.5, 5 and 10 µm scans. Integrating a PSD over 0.01 to 0.1 µm⁻¹ (optical-profiler band) can give an rms roughness more than an order of magnitude above a 1 µm × 1 µm AFM scan. **[snippet][peer / patent]** — [JJAP Conf. Proc. 1, 011005](https://www.jstage.jst.go.jp/article/jjapcp/1/0/1_011005/_article); [US 5955654, Calibration standard for microroughness measuring instruments](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5955654)

Correlation and reference role:

- 3D-AFM is described as serving three roles: validating CD-SEM and OCD, inline depth monitoring, and replacing TEM for engineering analysis. **[snippet][peer]** — [SPIE profile, Tianming Bao](https://astronomicaltelescopes.spiedigitallibrary.org/profile/Tianming.Bao-75460)
- Hybrid metrology is defined as using two or more toolsets together on the same data; OCD, CD-SEM and CD-AFM are usually run separately in fabs; data matching between toolsets is a key issue and results are verified against AFM, XSEM and TEM references. **[snippet][peer]** — [SPIE 7971, A holistic metrology approach: hybrid metrology utilizing scatterometry, CD-AFM and CD-SEM](https://spiedigitallibrary.org/conference-proceedings-of-spie/7971/1/A-holistic-metrology-approach--hybrid-metrology-utilizing-scatterometry-CD/10.1117/12.881632.full)
- AFM-trained ML scatterometry for Cu recess (SPIE 2026) and OCD "correlation to AFM" claims are listed in section 1. — [Nova-hosted SPIE 2026 paper](https://www.novami.com/wp-content/uploads/2026/04/13981-16-timoney-spie-alp-2026-vts-ml-cu-recess-final.pdf)
- For 3D NAND high-aspect-ratio structures, trade press points to IRCD and CD-SAXS as the nearest inline candidates with FIB-SEM or TEM for offline accuracy; AFM is not named as the solution there. **[snippet][trade press]** — [Semiconductor Engineering, How Metrology Tools Stack Up In 3D NAND Devices](https://semiengineering.com/how-metrology-tools-stack-up-in-3d-nand-devices)
- Profilometer dishing results are verified against AFM in CMP literature. **[snippet][peer]** — [MIT (Boning group), Overview of Methods](https://boning.mit.edu/wp-content/uploads/2022/11/Overview-of-Methods-for-Characterization-of-Pattern-De­pendencies-in-Copper-CMP.pdf)

### Inferences

- From per-site summary numbers alone an application can provide: per-parameter SPC by recipe and tool; within-wafer maps and a radial (centre-to-edge) profile; wafer-to-wafer and lot-to-lot trends; a dishing-versus-line-width or erosion-versus-density chart when the recipe's sites encode structure type; and a correlation view against another metrology on shared wafers with Mandel slope, offset and residual.
- Because AFM is the training reference for OCD and ML models, the quality of the AFM label set matters downstream. An "AFM reference set" view that shows which measurements are trustworthy (tip age, tool state, repeatability at the time) is a natural extension of tip and tool-health tracking.
- Pattern-dependence analysis needs structure metadata per site (line width, density, isolated or array). If the recipe naming or site labels carry it, the analysis is possible without raw data.

### Gaps

- No source found describing SPC rule sets or control-limit practice specific to AFM parameters.
- No DRAM or 3D NAND specific numbers for dishing, erosion or recess uniformity.
- ISO 25178-2 normative formulas were not read from the standard itself. Unverified background, to be checked against ISO 25178-2:2021 before implementation: Sq = sqrt((1/A)∬z² dx dy); Sa = (1/A)∬|z| dx dy; Ssk = (1/(Sq³A))∬z³ dx dy; Sku = (1/(Sq⁴A))∬z⁴ dx dy; Sdq = sqrt((1/A)∬((∂z/∂x)²+(∂z/∂y)²) dx dy); Sdr = (developed area − A)/A; Sal = shortest lag at which the areal autocorrelation falls to 0.2. Heights are relative to the mean plane after form removal.
- Mandel/TMU formulas were not read from a primary paper. Unverified background (Sendelbach and Archie, SPIE 2003, not retrieved): with λ = σ²_ref/σ²_test, slope β = [S_yy − λS_xx + sqrt((S_yy − λS_xx)² + 4λS_xy²)] / (2S_xy), offset = ȳ − βx̄, and TMU = 3·sqrt(σ²_Mandel − σ²_RMS) where σ_Mandel is the net residual about the fit and σ_RMS the reference system uncertainty.
- ISO 4287 and ISO 21920 definitions were not retrieved.

## 5. Throughput and usage: utilisation, recipe time, sampling, failures

### Takeaway

Throughput is the central weakness vendors compete on, and the only numbers available are vendor headline rates; I found no published account of how fabs analyse AFM utilisation, queue time, sampling plans or recipe failure modes.

### Cited Findings

- Bruker InSight AFP: 260 to 340 sites per hour for inline applications; up to 50 wafers per hour; profiling speed up to 36,000 µm/s; depth-mode move-acquire-measure under 10 s; recipe writing in under 5 minutes via an XML/CAD interface; recipes built off-tool and shared by XML. **[read][vendor]** — [Bruker InSight AFP](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-afp.html)
- Bruker AN5001: ERO at more than 45 wafers per hour for 8 sites; full 300 mm diameter profiles at up to 25 mm/s giving tens of wafers per hour. **[read][vendor]** — [Bruker AN5001](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/resource-library/an-5001-surface-metrology-for-hybrid-bonding-in-advanced-semiconductor-packaging.html)
- Park NX-Wafer automated sequence: wafer loading, auto probe exchange (with tip-position check), wafer alignment, tip approach, measurement and analysis by preset recipe; ADR is claimed to raise throughput "by up to 1,000%" by removing stage calibration against the inspection tool. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf)
- Park tool receives a recipe from the host, selects the tip, scans multiple targets, analyses and generates reports; automatic tip exchange success rate advertised at 99.9%. **[snippet][vendor]** — [Park NX-Wafer product page](https://www.parksystems.com/products/industrial/park-wafer/applications)
- Nearfield Instruments claims Lightning Mode gives more than 160 times faster image acquisition than existing automated AFM. **[snippet][vendor press release, unverified]** — [Nearfield Lightning Mode release, 2024](https://www.generation-nt.com/communiques-presse/nearfield-instruments-eur-quadra-in-line-semiconductor-metrology-2048804)
- Research: a multi-probe single-chip AFM system reported about 60 wafers per hour for five-site measurement on 4-inch wafers and argues traditional tip-based approaches are poorly suited to inline inspection speeds. **[snippet][peer]** — [Yao, Connolly et al., JM3 2019](https://ndml.me.utexas.edu/sites/default/files/publications/yao_connolly_jm3_2019.pdf)

### Inferences

- The automated sequence gives the natural failure taxonomy for a recipe success/failure analysis: wafer load, tip exchange, tip-position check, wafer alignment or pattern recognition, tip approach, scan, analysis. Counting failures per step, per recipe and per tool is feasible from tool logs if step outcomes are recorded.
- Since vendors quote sites per hour, the comparable in-house metric is achieved sites per hour and seconds per site by recipe, against which tip-exchange and qualification overhead can be shown separately.
- Tip qualification itself consumes tool time (NIST used one qualification per 10 measurements); the share of tool time spent on qualification versus product is a utilisation lever no vendor page quantifies.

### Gaps

- No source on AFM sampling-plan optimisation, queue-time analysis, or utilisation analytics in fabs.
- No published failure-rate data for auto approach or pattern-recognition steps other than Park's 99.9% tip-exchange claim.
- Semiconductor Engineering and Semiconductor Digest practitioner articles on AFM throughput pain points were searched for and not found.

## 6. Commercial software and tool capabilities

### Takeaway

Both major inline vendors advertise the same core loop — host-delivered recipe, automatic tip selection and exchange, pattern-recognition site alignment, automatic analysis and report — and differ mainly in tip strategy (Park: non-contact to avoid wear; Bruker: automated probe-shape qualification and a 100-tip store). Neither publishes detail on cross-tool or tip-population analytics, which is where an in-house tool is least likely to duplicate vendor software.

### Cited Findings

Park Systems:

- NX-Wafer: automatic data acquisition and analysis of trench width, depth and angle; EFEM wafer handling; remote control interface; automatic probe exchange; Cognex pattern recognition; ADR with defect-map import, survey and zoom-in scans and automated defect-type analysis; long-range profiler; live monitoring and markless target positioning. **[read][vendor]** — [Park NX-Wafer brochure PDF](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf); **[snippet]** [Park NX-Wafer product page](https://www.parksystems.com/products/industrial/park-wafer/applications)
- Park XEA: automation software in which a process-control engineer defines procedures in custom recipe files; combines optical pattern recognition with AFM for automated acquisition and analysis; most common automated measurements are roughness, trench width, depth and angle. Worked example: a reference site used to build the recipe, four further sites measured automatically, features with 10 µm pitch and 120 nm step height. **[snippet][vendor]** — [Park, Fully Automated AFM Measurement and Analysis Using Park NX System](https://www.parksystems.com/en/learning-center/lc-detail.learning163)
- Park SmartAnalysis (offline): region roughness statistics; up to 10 lines on an image for height and roughness along lines; customisable reports. **[snippet][vendor]** — [Park, Effortless AFM data analysis with Park SmartAnalysis](https://www.parksystems.com/en/learning-center/lc-detail.learning122)

Bruker:

- InSight AFP: listed in sections 1, 3 and 5; also compatible with KLARITY and most other yield-management systems for defect review; XML recipe sharing; hot-spot detection and review. **[read][vendor]** — [Bruker InSight AFP](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-afp.html)
- InSight 300: TipX, automatic probe-shape qualification, 100-tip capacity, recipe-controlled tip management and resource tracking, off-tool recipe creation. **[snippet][vendor]** — [Bruker InSight 300](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/insight-300.html)
- InSight CAP: recipe-based automatic measurement for 4, 6 and 8 inch wafers, SPC and batch analysis, integrated tip management and qualification. **[snippet][institute]** — [Fraunhofer ENAS](https://www.enas.fraunhofer.de/en/Business_Units/Cross-Functional_Topics/Fab-Management/InlineMetrology_and_Data/atomic-force-microscopy.html)
- NanoScope software automates bevel/ERO analysis (Δh between regions R1, R2 and a reference region). **[read][vendor]** — [Bruker AN5001](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/resource-library/an-5001-surface-metrology-for-hybrid-bonding-in-advanced-semiconductor-packaging.html)

Third-party analysis:

- Gwyddion: free, open-source SPM analysis for height fields with standard statistical characterisation, levelling, data correction, filtering and grain marking; reads many SPM formats, with content-based type detection; recent 2.71 and 3.x releases mainly extend format support. **[snippet][project documentation]** — [Gwyddion home](https://gwyddion.net/); [Gwyddion user guide, Managing Files](https://gwyddion.net/documentation/user-guide-en/managing-files.html)

### Inferences

- Features vendors do advertise on-tool (per-measurement analysis, per-recipe reports, tip exchange on threshold) are low-value to rebuild. Features absent from every vendor page I read — cross-tool comparison, tip-population statistics across a tool group, long-horizon trends joined with tip and tool events, correlation to other metrology — are the candidate gaps for an in-house application.
- The parameter vocabulary vendors emit (Height, Width, Interval, Pitch, Angle L/R, peak-to-valley, RMS roughness, ΔX/ΔY cursor pairs, R1/R2 Δh) indicates what key/value result text from tools is likely to contain and therefore what can be trended without raw data.

### Gaps

- Hitachi High-Tech AFM, Oxford Instruments / Asylum, NX-3DM, Park SmartScan for industrial tools, and MountainsSPIP / Digital Surf were not researched; no claims are made about them.
- No vendor documentation found describing group-level (multi-tool) dashboards or tip-population management software, so "vendors do not offer it" is an absence of evidence in public pages, not a confirmed absence.
- SECS/GEM and data-export specifics were not stated in the documents read.

## 7. Machine learning and emerging methods

### Takeaway

Demonstrated: image-level artefact or defect classification on AFM images (including a tip-contamination class), ML-regularised blind tip reconstruction, and AFM-trained ML scatterometry for Cu recess. Not demonstrated in what I found: a production-grade tip-condition classifier, AFM virtual metrology, or validated inline super-resolution; dataset scarcity is the stated obstacle.

### Cited Findings

- AFM_YOLO-ResNet (IEEE Access, 2024): detection and classification framework for AFM imaging defects. **[snippet][peer]** — [DOAJ record](https://doaj.org/article/be776a1212044a21802b7ac1ddd5c55b)
- Vision classifier plus LLM assistant for AFM defect classification: 91.43% overall accuracy, 93% recall for tip contamination, 60% recall for not-tracking; notes the lack of high-quality AFM datasets. **[snippet][project page, not peer-reviewed as found]** — [Conversational LLM-Based Decision Support for Defect Classification in AFM Images](https://jrrade-afm-defect-detection-llm-page.static.hf.space/)
- 2026 arXiv preprint (Iowa State): classifier first decides whether an image has artefacts, then a lightweight segmentation network produces artefact masks for restoration; targets scan-line distortions, streaks, pits, sample-induced anomalies. **[snippet][preprint]** — [arXiv 2602.04051](https://arxiv.org/html/2602.04051v1)
- APS March Meeting 2023 abstract: ML classification of artefact-free versus artefact images in PeakForce QNM data. **[snippet][abstract]** — [APS abstract M36.2](https://archive.aps.org/mar/2023/m36/2)
- End-to-end differentiable BTR with regularisation for noisy images (Scientific Reports, 2023). **[snippet][peer]** — [PMC9813222](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9813222/)
- Tip-state classification by ML exists for STM (Nottingham thesis), not AFM. **[snippet][thesis]** — [Machine learning at the nanoscale](https://eprints.nottingham.ac.uk/67430)
- AFM-trained ML scatterometry model for Cu recess, single model across top and bottom wafers (SPIE 2026). **[snippet][peer, vendor-hosted]** — [Nova-hosted SPIE 2026 paper](https://www.novami.com/wp-content/uploads/2026/04/13981-16-timoney-spie-alp-2026-vts-ml-cu-recess-final.pdf)

### Inferences

- Image-level artefact classification works on rendered images, since the published classifiers take images as input; it is the ML method most compatible with an archive of rendered images.
- All artefact classifiers found are trained on research-lab images, not inline semiconductor recipes; transfer to fab images would need a locally labelled set.
- The most mature "ML on AFM" pattern in fabs runs the other way: AFM as label source for optical models.

### Gaps

- No paper found whose main task is classifying AFM tip condition (blunt, double, contaminated) from images.
- No AFM-specific virtual metrology, automatic-levelling ML, or validated fast-scan super-resolution results were found; the Nearfield speed claim is a hardware/vendor claim, not an ML result.
- Attribution discrepancy: Nova's blog and a SEMICON Taiwan flyer credit the Cu-recess work as co-developed with Micron, while the hosted paper lists IBM Research and Nova authors. — [Nova blog](https://novami.com/blog/advancing-3d-integration-and-beol-scaling-novas-metrology-innovations-at-spie-2026/)

## 8. Rendered images plus summary numbers versus raw height maps; file formats

### Takeaway

Trend, SPC, wafer-map, tip-life, tool-health, correlation and usage analytics need only stored numeric results and metadata; anything that recomputes a measurement (re-levelling, new roughness parameters, PSD, blind tip reconstruction, profile re-extraction) needs the height array. Raw arrays are recoverable from the vendors' native files with open tooling: Gwyddion reads Park `.tiff` and Bruker Nanoscope `.spm`.

### Cited Findings

- Gwyddion supported-formats table: Park Systems `.tiff`/`.tif` read by module `psia` (read only); Park PS-PPT `.ps-ppt` read by `psppt` (with curve-map support); Veeco/Bruker Nanoscope III `.spm`, `.001`, `.002`… read by `nanoscope` (volume and curve-map supported, point spectra limited, positional information lost); Hitachi AFM `.afm` read by `hitachi-afm`; Seiko SII `.xqb/.xqd/.xqt/.xqp/.xqj/.xqi`; Asylum/Igor `.ibw` read and write; SPIP ASCII `.asc` read and write; Image Metrology `.bcr/.bcrf`; Surf `.sur`. **[read][project documentation]** — [Gwyddion user guide, Supported File Formats](https://gwyddion.net/documentation/user-guide-en/file-formats.html)
- Generic pixmap images (`.png`, `.jpeg`, `.tiff`, `.tga`, `.pnm`, `.bmp`) can be imported by Gwyddion via Gdk-Pixbuf; pixmap export is "usually lossy, intended for presentational purposes", with 16-bit greyscale export possible to PNG, TIFF and PNM. **[read][project documentation]** — [Gwyddion user guide, Supported File Formats](https://gwyddion.net/documentation/user-guide-en/file-formats.html)
- A Python package `afmreader` lists a Park `.tiff` reader as "To Be Implemented", i.e. Python-side Park support is less mature than Gwyddion's. **[snippet][package page]** — [afmreader on PyPI](https://pypi.org/project/afmreader)
- BTR and tip-radius-from-peaks methods operate on the height image (section 2). — [arXiv 1105.1472](https://arxiv.org/pdf/1105.1472); [Vorselen et al.](https://www.nature.com/articles/srep36972)
- Rq depends on scan size and sampling interval, and different-bandwidth values are not comparable without the PSD (section 3). — [SPIE 7656](https://spiedigitallibrary.org/conference-proceedings-of-spie/7656/76562D/Comparison-of-optical-surface-roughness-measured-by-stylus-profiler-AFM/10.1117/12.863268.full)

### Inferences

Possible from summary numerics and metadata only:

- SPC and trends per parameter, recipe, tool, tip.
- Within-wafer maps, radial profiles, wafer-to-wafer and lot-to-lot comparison.
- Tip-life tracking: usage counters, qualifier or monitor-site results against usage, exchange-event overlays, per-tip-type life distributions.
- Tool health and matching from reference-sample results; Mandel/TMU correlation to other metrology.
- Usage, recipe run time and step-failure statistics.
- Dishing-versus-width and erosion-versus-density charts when site labels carry structure type.

Possible from rendered images, with limits:

- Visual review, side-by-side and gallery comparison, human annotation.
- Image-level artefact or defect classification (published classifiers are image-based).
- Not quantitative height: a rendered image has a colour map, usually per-image auto-scaling and 8-bit depth, so height cannot be recovered reliably unless the colour scale, range and lossless encoding are known. Any roughness or step value computed from it would be an estimate of unknown bias.

Strictly needs raw height arrays:

- Re-levelling or re-flattening and any recomputation of step height, depth, dishing or erosion with a different reference region.
- ISO 25178 parameters beyond those the tool reported (Ssk, Sku, Sdq, Sdr, Sal), PSD and spatial-frequency analysis, autocorrelation.
- Blind tip reconstruction and tip-radius estimation from product images.
- Profile overlays at true scale across sites, wafers and lots (unless the tool exports profile data as numbers).
- Sidewall angle and sidewall roughness recomputation.

### Gaps

- Internal structure of the Park `.tiff` (how the height array and header are embedded) and the Bruker `.spm` header was not read from a specification; the evidence here is that Gwyddion's `psia` and `nanoscope` modules read them. A Python route (for example reading the Park TIFF custom tags directly) was not verified.
- Whether a tool's rendered image export is lossless and carries a fixed height scale is tool- and recipe-specific and cannot be answered from external sources.
- Gwyddion's documentation as read says nothing about height calibration when importing pixmap images.
