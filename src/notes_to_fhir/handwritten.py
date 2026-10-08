"""Twenty hand-written notes: the held-out test set.

The template notes in generate.py follow a few fixed layouts, and a rule-based
extractor written against them scores close to 100%. These notes were written
afterwards, one at a time, in the styles real notes come in: dictation with
numbers spelled out, referral letters, ED shorthand, nicknames, two-word given
names, doses in grams, glucose in mmol/L, plans that change what the medication
list says. The rule-based baseline was frozen (git history) before they existed.

All patients are fictional.
"""

from __future__ import annotations


def pt(given, family, gender, dob):
    return {"given_name": given, "family_name": family, "gender": gender, "birth_date": dob}


def cond(name, status="active"):
    return {"name": name, "clinical_status": status}


def med(name, dose=None, unit=None, route=None, freq=None, status="active"):
    return {"name": name, "dose_value": dose, "dose_unit": unit, "route": route,
            "frequency": freq, "status": status}


def alg(substance, reaction=None):
    return {"substance": substance, "reaction": reaction}


def obs(name, value, unit=None):
    return {"name": name, "value": value, "unit": unit}


def bp(sys, dia):
    return [obs("systolic blood pressure", sys, "mmHg"), obs("diastolic blood pressure", dia, "mmHg")]


def note(id, text, patient, conditions, medications, allergies, observations, traps):
    return {"id": id, "style": "handwritten", "traps": traps, "text": text.strip(),
            "gold": {"patient": patient, "conditions": conditions, "medications": medications,
                     "allergies": allergies, "observations": observations}}


NOTES = [
    note("hw-01", """
Pt: Hailu, Meron    DOB 7/2/1958    F
CC: "my sugars are running high"
HPI: 67 y/o woman with longstanding type 2 DM and HTN here because home fingersticks have been 200-250 for the past 2 weeks. Taking metformin 1000 BID and lisinopril 20 daily, no missed doses. Pt denies chest pain or SOB. Her sister was recently diagnosed with breast ca.
Allergies: penicillin - throat swelling as a child
Exam: BP 152/88  HR 84  T 98.1  Wt 176 lbs  SpO2 98% RA
Labs: A1c 9.1 (was 7.8 last fall), glucose 236
A/P:
1. T2DM, uncontrolled - add Lantus 10 units qHS, continue metformin.
2. HTN - above goal, increase lisinopril to 40 mg daily.
RTC 4 wks.
""",
         pt("Meron", "Hailu", "female", "1958-07-02"),
         [cond("type 2 diabetes"), cond("hypertension")],
         [med("metformin", 1000, "mg", None, "twice daily"),
          med("lisinopril", 40, "mg", None, "once daily"),
          med("insulin glargine", 10, "units", None, "at bedtime")],
         [alg("penicillin", "swelling")],
         [*bp(152, 88), obs("heart rate", 84, "/min"), obs("body temperature", 98.1, "degF"),
          obs("body weight", 176, "lb"), obs("oxygen saturation", 98, "%"),
          obs("hemoglobin a1c", 9.1, "%"), obs("glucose", 236, "mg/dL")],
         {"dose_change": ["lisinopril"], "new_med": ["insulin glargine"], "prior_value": ["hemoglobin a1c"],
          "brand_name": ["insulin glargine"], "family_history": ["breast cancer"],
          "unit_conversion": ["body temperature", "body weight"]}),

    note("hw-02", """
Telehealth visit 03/04/2026
Name: Carlos Mendoza | DOB: 1990-11-23 | male
S: 35M f/u depression and anxiety (GAD). Started on Zoloft 50 mg in December, feels about 50% better, sleeping ok. Wants to go up on the dose. No SI/HI. Quit the buspirone in January bc it made him dizzy. Had asthma as a kid, none since age 12 and no inhaler in years.
Meds: sertraline 50 mg PO daily
NKDA
O: video visit, no vitals.
A/P: MDD - improving; increase sertraline to 100 mg daily. GAD - stable. Childhood asthma, resolved.
""",
         pt("Carlos", "Mendoza", "male", "1990-11-23"),
         [cond("major depressive disorder"), cond("generalized anxiety disorder"), cond("asthma", "resolved")],
         [med("sertraline", 100, "mg", "oral", "once daily"), med("buspirone", status="stopped")],
         [],
         [],
         {"dose_change": ["sertraline"], "stopped_med": ["buspirone"], "resolved": ["asthma"]}),

    note("hw-03", """
CARDIOLOGY FOLLOW-UP
Patient: Gebremedhin, Yohannes (M), DOB Feb 9, 1949. Seen 6/12/2026.
77M with persistent AF on Eliquis, HFrEF (EF 35%), CAD s/p stent 2019, and CKD 3a. Reports mild ankle edema. No syncope. Never had a stroke.
Current regimen: apixaban 5 mg bid; metoprolol succinate 50 mg daily; furosemide 40 mg qAM; atorvastatin 80 mg at night; aspirin 81 daily.
Warfarin was stopped in 2021 due to labile INRs.
Allergies: sulfa (rash), iodinated contrast (hives)
Vitals: 134/78, HR 72 irregular, RR 16, O2 sat 96%, wt 92.3 kg
Labs today: creatinine 1.6, LDL 64
Plan: stop aspirin given bleeding risk on apixaban. Continue others. Echo in 6 months.
""",
         pt("Yohannes", "Gebremedhin", "male", "1949-02-09"),
         [cond("atrial fibrillation"), cond("heart failure"), cond("coronary artery disease"),
          cond("chronic kidney disease")],
         [med("apixaban", 5, "mg", None, "twice daily"), med("metoprolol", 50, "mg", None, "once daily"),
          med("furosemide", 40, "mg", None, "once daily"), med("atorvastatin", 80, "mg", None, "at bedtime"),
          med("aspirin", 81, "mg", None, "once daily", "stopped"), med("warfarin", status="stopped")],
         [alg("sulfonamide", "rash"), alg("iodinated contrast", "hives")],
         [*bp(134, 78), obs("heart rate", 72, "/min"), obs("respiratory rate", 16, "/min"),
          obs("oxygen saturation", 96, "%"), obs("body weight", 92.3, "kg"),
          obs("creatinine", 1.6, "mg/dL"), obs("ldl cholesterol", 64, "mg/dL")],
         {"stopped_med": ["warfarin", "aspirin"], "negated": ["stroke"]}),

    note("hw-04", """
Discharge Summary
Pt name: Alemayehu Tsegaye   Sex: male   Birth date: 1956/03/30
Admitted 4/2/26 - 4/6/26 for COPD exacerbation triggered by community acquired pneumonia. Treated with IV antibiotics, then transitioned to oral amoxicillin. Also has GERD and high cholesterol. No hx of asthma.
Discharge meds:
 * Spiriva 18 mcg 1 cap inhaled once daily
 * albuterol inhaler 2 puffs q4h prn SOB
 * amoxicillin 875 mg by mouth twice daily x 5 more days
 * prednisone 40 mg daily x 3 more days
 * omeprazole 20 mg daily
 * simvastatin 40 mg qhs
Allergies: latex (itching)
Discharge vitals: T 37.0C, HR 88, BP 128/76, RR 18, SpO2 93% RA. Wt 64 kg.
Follow up with pulmonology in 2 weeks.
""",
         pt("Alemayehu", "Tsegaye", "male", "1956-03-30"),
         [cond("copd"), cond("pneumonia"), cond("gerd"), cond("hyperlipidemia")],
         [med("tiotropium", 18, "mcg", "inhaled", "once daily"),
          med("albuterol", 2, "puffs", "inhaled", "as needed"),
          med("amoxicillin", 875, "mg", "oral", "twice daily"),
          med("prednisone", 40, "mg", None, "once daily"),
          med("omeprazole", 20, "mg", None, "once daily"),
          med("simvastatin", 40, "mg", None, "at bedtime")],
         [alg("latex", "itching")],
         [obs("body temperature", 37.0, "Cel"), obs("heart rate", 88, "/min"), *bp(128, 76),
          obs("respiratory rate", 18, "/min"), obs("oxygen saturation", 93, "%"), obs("body weight", 64, "kg")],
         {"brand_name": ["tiotropium"], "negated": ["asthma"]}),

    note("hw-05", """
URGENT CARE
Fatuma Abdi, 29F, DOB 08/30/1996
c/o burning w/ urination x2 days, frequency. No fever, no flank pain. UPT neg.
PMH: migraines (uses sumatriptan prn, maybe twice a month). No other meds.
Allergic to cephalosporins -> hives, and Bactrim (rash).
Vitals: T 98.9 F, BP 118/74, P 92
UA: + leuks, + nitrites.
Dx: acute cystitis
Rx: Macrobid 100 mg PO BID x 5 days.
""",
         pt("Fatuma", "Abdi", "female", "1996-08-30"),
         [cond("migraine"), cond("urinary tract infection")],
         [med("sumatriptan", freq="as needed"), med("nitrofurantoin", 100, "mg", "oral", "twice daily")],
         [alg("cephalosporin", "hives"), alg("sulfonamide", "rash")],
         [obs("body temperature", 98.9, "degF"), *bp(118, 74), obs("heart rate", 92, "/min")],
         {"brand_name": ["nitrofurantoin"], "new_med": ["nitrofurantoin"], "unit_conversion": ["body temperature"]}),

    note("hw-06", """
Dear Dr. Okonkwo,

Thank you for referring Mrs. Lemlem Gebre (born 22 January 1971), whom I saw in endocrine clinic today.

She has primary hypothyroidism diagnosed in 2015 and has been on levothyroxine 112 mcg daily, taken on an empty stomach. Her TSH today was 6.8 mIU/L, up from 2.1 last year, so I have increased her levothyroxine to 125 mcg daily. She also has well-controlled GERD on pantoprazole 40 mg each morning, and osteoarthritis of both knees, for which she takes acetaminophen 1 g up to three times a day as needed.

Her mother had Alzheimer's dementia. She denies any history of diabetes. No known drug allergies.

On examination her blood pressure was 126/80, pulse 66, weight 70.5 kg and temperature 36.7 °C.

I will see her again in 8 weeks with a repeat TSH.

Sincerely,
Endocrinology
""",
         pt("Lemlem", "Gebre", "female", "1971-01-22"),
         [cond("hypothyroidism"), cond("gerd"), cond("osteoarthritis")],
         [med("levothyroxine", 125, "mcg", None, "once daily"),
          med("pantoprazole", 40, "mg", None, "once daily"),
          med("acetaminophen", 1, "g", None, "as needed")],
         [],
         [obs("tsh", 6.8, "mIU/L"), *bp(126, 80), obs("heart rate", 66, "/min"),
          obs("body weight", 70.5, "kg"), obs("body temperature", 36.7, "Cel")],
         {"dose_change": ["levothyroxine"], "prior_value": ["tsh"], "family_history": ["alzheimer disease"],
          "negated": ["type 2 diabetes"]}),

    note("hw-07", """
ED NOTE 9/14/2026 0215
42 yo M, Mohammed Yusuf (DOB 1984-05-17), presents w/ wheezing and SOB x 1 day. Hx asthma since childhood - uses ProAir prn (about 3x/week lately), Flovent HFA 220 mcg BID (admits poor adherence). No COPD. Not a smoker. FH: father - MI at 55.
NKDA.
VS: HR 108, BP 142/90, RR 24, SpO2 93% RA, T 99.1
Imp: asthma exacerbation, mild-moderate. CXR neg for pneumonia.
Plan: nebulizer treatments given in ED. Start prednisone 50 mg PO daily x 5d. Continue Flovent + albuterol PRN. D/c home.
""",
         pt("Mohammed", "Yusuf", "male", "1984-05-17"),
         [cond("asthma")],
         [med("albuterol", freq="as needed"), med("fluticasone", 220, "mcg", None, "twice daily"),
          med("prednisone", 50, "mg", "oral", "once daily")],
         [],
         [obs("heart rate", 108, "/min"), *bp(142, 90), obs("respiratory rate", 24, "/min"),
          obs("oxygen saturation", 93, "%"), obs("body temperature", 99.1, "degF")],
         {"negated": ["copd", "pneumonia"], "family_history": ["myocardial infarction"], "new_med": ["prednisone"],
          "brand_name": ["fluticasone", "albuterol"], "unit_conversion": ["body temperature"]}),

    note("hw-08", """
Home visit, 07/22/2026. Ms. Abeba Wolde, 84, DOB 03/03/1942.
Lives with daughter. Dx: Alzheimer's dementia (moderate), HTN, OA, hypothyroid. Daughter reports she is eating well. She no longer takes donepezil - family stopped it in spring because it caused nausea.
Meds per pill box: amlodipine 5 mg qd, levothyroxine 50 mcg qd, Tylenol 650 mg TID PRN for knee pain.
Allergies: codeine -> confusion
BP 148/70 sitting, HR 64, wt 118 lb. No falls since last visit. No hx of stroke.
Plan: increase amlodipine to 10 mg daily.
""",
         pt("Abeba", "Wolde", "female", "1942-03-03"),
         [cond("alzheimer disease"), cond("hypertension"), cond("osteoarthritis"), cond("hypothyroidism")],
         [med("donepezil", status="stopped"), med("amlodipine", 10, "mg", None, "once daily"),
          med("levothyroxine", 50, "mcg", None, "once daily"), med("acetaminophen", 650, "mg", None, "as needed")],
         [alg("codeine", "confusion")],
         [*bp(148, 70), obs("heart rate", 64, "/min"), obs("body weight", 118, "lb")],
         {"stopped_med": ["donepezil"], "dose_change": ["amlodipine"], "negated": ["stroke"],
          "brand_name": ["acetaminophen"], "unit_conversion": ["body weight"]}),

    note("hw-09", """
PRE-OPERATIVE EVALUATION
Name: Kevin O'Brien | Sex: M | DOB: 10/05/1967 | Date: 08/19/2026
Planned procedure: right total knee replacement for severe osteoarthritis.
PMH: obesity, OSA on CPAP, type 2 diabetes, HLD. No history of heart attack or heart failure. Denies prior anesthesia problems.
Meds: Jardiance 10 mg every morning, metformin 500 mg twice daily, rosuvastatin 20 mg daily, ibuprofen 600 mg prn knee pain.
Allergies: Latex (contact rash), morphine (itching).
Exam: Wt 252 lb, BP 136/84, HR 78, SpO2 95%.
Labs: HbA1c 7.2%, Cr 0.9, glucose 148.
Assessment: acceptable risk for surgery.
""",
         pt("Kevin", "O'Brien", "male", "1967-10-05"),
         [cond("osteoarthritis"), cond("obesity"), cond("obstructive sleep apnea"), cond("type 2 diabetes"),
          cond("hyperlipidemia")],
         [med("empagliflozin", 10, "mg", None, "once daily"), med("metformin", 500, "mg", None, "twice daily"),
          med("rosuvastatin", 20, "mg", None, "once daily"), med("ibuprofen", 600, "mg", None, "as needed")],
         [alg("latex", "rash"), alg("morphine", "itching")],
         [obs("body weight", 252, "lb"), *bp(136, 84), obs("heart rate", 78, "/min"),
          obs("oxygen saturation", 95, "%"), obs("hemoglobin a1c", 7.2, "%"), obs("creatinine", 0.9, "mg/dL"),
          obs("glucose", 148, "mg/dL")],
         {"negated": ["myocardial infarction", "heart failure"], "brand_name": ["empagliflozin"],
          "unit_conversion": ["body weight"]}),

    note("hw-10", """
Clinic note - 05/05/2026
Ana Lucia Ramirez, F, DOB May 30, 1955 (seen with Spanish interpreter)
New palpitations x 1 week. ECG today shows atrial fibrillation, rate 112. No chest pain. Hx HTN on losartan 50 daily and HCTZ 25 daily. Had a UTI in March, treated, resolved.
Allergies: none.
Vitals: BP 158/94, HR 112 irregularly irregular, T 98.4, wt 68 kg
Plan: start metoprolol tartrate 25 mg BID for rate control and apixaban 5 mg BID. TSH and BMP ordered. Echo.
""",
         pt("Ana Lucia", "Ramirez", "female", "1955-05-30"),
         [cond("atrial fibrillation"), cond("hypertension"), cond("urinary tract infection", "resolved")],
         [med("losartan", 50, "mg", None, "once daily"), med("hydrochlorothiazide", 25, "mg", None, "once daily"),
          med("metoprolol", 25, "mg", None, "twice daily"), med("apixaban", 5, "mg", None, "twice daily")],
         [],
         [*bp(158, 94), obs("heart rate", 112, "/min"), obs("body temperature", 98.4, "degF"),
          obs("body weight", 68, "kg")],
         {"new_med": ["metoprolol", "apixaban"], "resolved": ["urinary tract infection"],
          "unit_conversion": ["body temperature"]}),

    note("hw-11", """
Nephrology consult 2/11/2026
Pt: Desta, Haile; 71 yo M; DOB 1954-09-03
Reason: worsening kidney function. CKD stage 3b due to type 2 diabetes and hypertension. Cr 2.4 today (1.9 in Oct). He has been taking Motrin 600 mg several times a day - advised to stop all NSAIDs.
Meds: insulin glargine 24 units at bedtime, lisinopril 10 mg daily, amlodipine 10 mg daily, Lasix 20 mg daily
Allergies: shellfish - anaphylaxis
Vitals: BP 146/82 HR 70 Wt 88 kg
Labs: creatinine 2.4 mg/dL, glucose 9.2 mmol/L, HbA1c 7.9%
Plan: stop ibuprofen. Continue other meds. Renal ultrasound.
""",
         pt("Haile", "Desta", "male", "1954-09-03"),
         [cond("chronic kidney disease"), cond("type 2 diabetes"), cond("hypertension")],
         [med("insulin glargine", 24, "units", None, "at bedtime"), med("lisinopril", 10, "mg", None, "once daily"),
          med("amlodipine", 10, "mg", None, "once daily"), med("furosemide", 20, "mg", None, "once daily"),
          med("ibuprofen", 600, "mg", status="stopped")],
         [alg("shellfish", "anaphylaxis")],
         [*bp(146, 82), obs("heart rate", 70, "/min"), obs("body weight", 88, "kg"),
          obs("creatinine", 2.4, "mg/dL"), obs("glucose", 9.2, "mmol/L"), obs("hemoglobin a1c", 7.9, "%")],
         {"prior_value": ["creatinine"], "stopped_med": ["ibuprofen"], "brand_name": ["furosemide", "ibuprofen"],
          "unit_conversion": ["glucose"]}),

    note("hw-12", """
Allergy & Immunology
Patient: Liya Bekele  DOB 2004-01-15  Sex: F  Visit: 03/27/2026
21-year-old with peanut allergy (anaphylaxis at age 6, needed epinephrine) and egg allergy (hives), here for annual review. Also has mild intermittent asthma, uses albuterol about once a month. No eczema.
Meds: albuterol HFA 2 puffs q4-6h prn; EpiPen 0.3 mg IM prn anaphylaxis.
Allergies: peanuts (anaphylaxis), eggs (hives)
Vitals: BP 112/70, HR 68, SpO2 99%, weight 58 kg
Plan: continue to carry EpiPen at all times.
""",
         pt("Liya", "Bekele", "female", "2004-01-15"),
         [cond("asthma")],
         [med("albuterol", 2, "puffs", None, "as needed"), med("epinephrine", 0.3, "mg", "intramuscular", "as needed")],
         [alg("peanut", "anaphylaxis"), alg("egg", "hives")],
         [*bp(112, 70), obs("heart rate", 68, "/min"), obs("oxygen saturation", 99, "%"), obs("body weight", 58, "kg")],
         {"negated": ["atopic dermatitis"], "brand_name": ["epinephrine"]}),

    note("hw-13", """
Transfer of care note (hospitalist to SNF), 01/28/2026
Patient: Robert "Bob" Jenkins, male, born 11/11/1938
Admitted for CHF exacerbation, diuresed 6 L. Course complicated by AKI, now improving. Other problems: CAD, DM2 (diet-controlled), BPH. Pneumonia in 2023, resolved.
Meds at transfer: furosemide 40 mg PO BID (increased from daily), carvedilol 3.125 mg BID, aspirin 81 mg daily, tamsulosin 0.4 mg qhs. Lisinopril d/c'd due to AKI. Not on metformin.
Allergies: Morphine (nausea/vomiting)
Last vitals: T 36.8, BP 108/62, HR 74, RR 18, SpO2 95% RA, weight 79.4 kg (admit weight 85.4 kg). Cr 1.5 (peak 2.3).
""",
         pt("Robert", "Jenkins", "male", "1938-11-11"),
         [cond("heart failure"), cond("acute kidney injury"), cond("coronary artery disease"),
          cond("type 2 diabetes"), cond("benign prostatic hyperplasia"), cond("pneumonia", "resolved")],
         [med("furosemide", 40, "mg", "oral", "twice daily"), med("carvedilol", 3.125, "mg", None, "twice daily"),
          med("aspirin", 81, "mg", None, "once daily"), med("tamsulosin", 0.4, "mg", None, "at bedtime"),
          med("lisinopril", status="stopped")],
         [alg("morphine", "nausea")],
         [obs("body temperature", 36.8, "Cel"), *bp(108, 62), obs("heart rate", 74, "/min"),
          obs("respiratory rate", 18, "/min"), obs("oxygen saturation", 95, "%"), obs("body weight", 79.4, "kg"),
          obs("creatinine", 1.5, "mg/dL")],
         {"prior_value": ["body weight", "creatinine"], "stopped_med": ["lisinopril"], "resolved": ["pneumonia"]}),

    note("hw-14", """
Annual exam - 02/19/2026
Ms. Sara Tesfaye is a 38-year-old (DOB 6/14/1987) with no chronic illnesses except iron-deficiency anemia from heavy periods, on ferrous sulfate 325 mg every other day. She also gets occasional migraines with aura and uses ibuprofen 400 mg as needed. She had gestational diabetes in 2019, which resolved after delivery. Her mother has hypertension and type 2 diabetes. Allergies: none known.
BP 104/66, HR 72, weight 141 lb.
Plan: continue iron, recheck CBC in 3 months.
""",
         pt("Sara", "Tesfaye", "female", "1987-06-14"),
         [cond("iron deficiency anemia"), cond("migraine"), cond("gestational diabetes", "resolved")],
         [med("ferrous sulfate", 325, "mg", None, "every other day"), med("ibuprofen", 400, "mg", None, "as needed")],
         [],
         [*bp(104, 66), obs("heart rate", 72, "/min"), obs("body weight", 141, "lb")],
         {"family_history": ["hypertension", "type 2 diabetes"], "resolved": ["gestational diabetes"],
          "unit_conversion": ["body weight"]}),

    note("hw-15", """
this is a follow up visit for mr abdi hassan date of birth september 3rd 1960 he is a 65 year old gentleman with hypertension and high cholesterol and gout he takes amlodipine ten milligrams once a day atorvastatin forty milligrams at night and allopurinol three hundred milligrams daily he stopped taking his colchicine because of diarrhea he has no allergies to medications blood pressure today one thirty two over eighty two pulse seventy weight two hundred and five pounds uric acid was 6.1 his brother has prostate cancer plan continue current medications
""",
         pt("Abdi", "Hassan", "male", "1960-09-03"),
         [cond("hypertension"), cond("hyperlipidemia"), cond("gout")],
         [med("amlodipine", 10, "mg", None, "once daily"), med("atorvastatin", 40, "mg", None, "at bedtime"),
          med("allopurinol", 300, "mg", None, "once daily"), med("colchicine", status="stopped")],
         [],
         [*bp(132, 82), obs("heart rate", 70, "/min"), obs("body weight", 205, "lb"), obs("uric acid", 6.1, "mg/dL")],
         {"stopped_med": ["colchicine"], "family_history": ["prostate cancer"], "unit_conversion": ["body weight"]}),

    note("hw-16", """
BEHAVIORAL HEALTH DISCHARGE
Name: Tomas Herrera   DOB: 04/18/1995   Gender: M
Dx: Major depressive disorder, recurrent, severe without psychotic features; generalized anxiety disorder; insomnia.
Meds on discharge: escitalopram 20 mg daily (increased from 10 mg), trazodone 50 mg nightly, hydroxyzine 25 mg TID prn anxiety.
Discontinued: sertraline (ineffective).
Allergies: NKDA. Vitals at discharge: BP 122/78, HR 80, T 98.0 F, wt 75 kg.
No suicidal ideation at discharge. No history of bipolar disorder.
""",
         pt("Tomas", "Herrera", "male", "1995-04-18"),
         [cond("major depressive disorder"), cond("generalized anxiety disorder"), cond("insomnia")],
         [med("escitalopram", 20, "mg", None, "once daily"), med("trazodone", 50, "mg", None, "at bedtime"),
          med("hydroxyzine", 25, "mg", None, "as needed"), med("sertraline", status="stopped")],
         [],
         [*bp(122, 78), obs("heart rate", 80, "/min"), obs("body temperature", 98.0, "degF"), obs("body weight", 75, "kg")],
         {"dose_change": ["escitalopram"], "stopped_med": ["sertraline"], "negated": ["bipolar disorder"],
          "unit_conversion": ["body temperature"]}),

    note("hw-17", """
Pt: Kebede Ayana | M | DOB 1979-12-01 | 2026-09-02
Known HTN, T2DM x 8 yrs. Came for refill. Taking metformin 850mg bid, glibenclamide 5mg qd, enalapril 10mg bid.
No known allergy.
BP 138/86, PR 80, Temp 36.5, Wt 74kg
FBS 168 mg/dl
Plan: add amlodipine 5mg daily. Advised on diet and exercise.
""",
         pt("Kebede", "Ayana", "male", "1979-12-01"),
         [cond("hypertension"), cond("type 2 diabetes")],
         [med("metformin", 850, "mg", None, "twice daily"), med("glyburide", 5, "mg", None, "once daily"),
          med("enalapril", 10, "mg", None, "twice daily"), med("amlodipine", 5, "mg", None, "once daily")],
         [],
         [*bp(138, 86), obs("heart rate", 80, "/min"), obs("body temperature", 36.5, "Cel"),
          obs("body weight", 74, "kg"), obs("glucose", 168, "mg/dL")],
         {"new_med": ["amlodipine"], "brand_name": ["glyburide"]}),

    note("hw-18", """
Survivorship visit 04/09/2026
Name: Helen Park, female, DOB 1962-02-14
History of left breast cancer, stage I, s/p lumpectomy and radiation in 2018, no evidence of recurrence. Completed 5 years of anastrozole in 2023. Other: osteoporosis on alendronate 70 mg weekly; hypothyroidism on levothyroxine 75 mcg daily. Her sister had ovarian cancer.
Allergy: iodine contrast -> hives.
Vitals: BP 118/72, HR 70, Wt 59.2 kg. Labs: TSH 2.4
Plan: annual mammogram, DEXA in 2 years.
""",
         pt("Helen", "Park", "female", "1962-02-14"),
         [cond("breast cancer", "resolved"), cond("osteoporosis"), cond("hypothyroidism")],
         [med("anastrozole", status="stopped"), med("alendronate", 70, "mg", None, "weekly"),
          med("levothyroxine", 75, "mcg", None, "once daily")],
         [alg("iodinated contrast", "hives")],
         [*bp(118, 72), obs("heart rate", 70, "/min"), obs("body weight", 59.2, "kg"), obs("tsh", 2.4, "mIU/L")],
         {"resolved": ["breast cancer"], "stopped_med": ["anastrozole"], "family_history": ["ovarian cancer"]}),

    note("hw-19", """
ADMISSION H&P 10/01/2026
Pt: Getachew Mulu, 58M, DOB 02/28/1968
CC: fever, productive cough
HPI: 3 days of fever up to 102, cough with green sputum, pleuritic chest pain. CXR: RLL consolidation. Dx community-acquired pneumonia.
PMH: COPD (on Spiriva), HTN, GERD.
Home meds: tiotropium 18 mcg inhaled daily, lisinopril 20 mg daily, omeprazole 20 mg daily
Allergies: PCN (hives)
Vitals: T 38.9 C, HR 104, BP 132/80, RR 24, SpO2 90% on RA
Labs: glucose 132, creatinine 1.1
Plan: admit. Ceftriaxone 1 g IV q24h + azithromycin 500 mg IV daily.
""",
         pt("Getachew", "Mulu", "male", "1968-02-28"),
         [cond("pneumonia"), cond("copd"), cond("hypertension"), cond("gerd")],
         [med("tiotropium", 18, "mcg", "inhaled", "once daily"), med("lisinopril", 20, "mg", None, "once daily"),
          med("omeprazole", 20, "mg", None, "once daily"), med("ceftriaxone", 1, "g", "intravenous", "once daily"),
          med("azithromycin", 500, "mg", "intravenous", "once daily")],
         [alg("penicillin", "hives")],
         [obs("body temperature", 38.9, "Cel"), obs("heart rate", 104, "/min"), *bp(132, 80),
          obs("respiratory rate", 24, "/min"), obs("oxygen saturation", 90, "%"), obs("glucose", 132, "mg/dL"),
          obs("creatinine", 1.1, "mg/dL")],
         {"new_med": ["ceftriaxone", "azithromycin"], "prior_value": ["body temperature"]}),

    note("hw-20", """
Rx refill request - 08/08/2026. Pt Yared Getahun (DOB 1/9/2000, M) requests refill of escitalopram 10 mg daily for anxiety (GAD). Last seen 3 months ago, stable. Refilled x 90 days. Allergies: NKDA.
""",
         pt("Yared", "Getahun", "male", "2000-01-09"),
         [cond("generalized anxiety disorder")],
         [med("escitalopram", 10, "mg", None, "once daily")],
         [],
         [],
         {}),
]
