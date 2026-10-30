"""Cases taken from real inbox subjects and previews (sender, subject, start of body)."""
import unittest

from tracker.job_emails import (
    ASSESSMENT, CONFIRMATION, INTERVIEW, OFFER, OTHER, REJECTED, VERIFICATION, classify, extract, tidy_company,
    tidy_role,
)
from tracker.models import Email

# sender, subject, body, kind, company, role ("" = don't check)
CASES = [
    ("copart@myworkday.com", "Thank You For Applying!", "Thank you for applying.", CONFIRMATION, "Copart", ""),
    ("selinc@myworkday.com", "Thank you for your application", "We received it.", CONFIRMATION,
     "Schweitzer Engineering Laboratories (SEL)", ""),
    ("Wipro Notifications <notifications@broadcast.wipro.com>", "Your One-Time Password (OTP) for Profile Creation",
     "Your One-Time Password (OTP) is 452323. To proceed, please visit our candidate portal and enter the OTP.",
     VERIFICATION, "", ""),
    ("systemmessage@paycomonline.com", "Verify Your Email",
     "Thank you for creating an account with ANDREW WOMMACK MINISTRIES INC! Use the 6-digit code", VERIFICATION, "", ""),
    ("United Airlines <notifications@united.com>", "Here's your verification code",
     "Your verification code is 123456.", OTHER, "", ""),
    ("GitHub <noreply@github.com>", "[GitHub] Sudo email verification code",
     "Here is your GitHub sudo authentication code", OTHER, "", ""),
    ("donotreply_ms workday <ms@myworkday.com>", "Thank You for Your Application!",
     "Dear Naman,\nThank you for your interest in the AI Development Solution Engineer\n- Associate position.\n"
     "Kind Regards,\nMorgan Stanley Talent Acquisition", CONFIRMATION, "Morgan Stanley", ""),
    ("BCI Brands <noreply@candidates.workablemail.com>", "Halogen Assistant Designer - BCI Brands",
     "Hi Naman Dewan,\nWe have received your application to BCI Brands and are currently in the\n"
     "process of reviewing", CONFIRMATION, "BCI Brands", ""),
    ("no-reply@us.greenhouse-mail.io", "Thank you for applying to Ascent Developer Solutions",
     "Naman,\nThanks for applying to Ascent Developer Solutions.", CONFIRMATION, "Ascent Developer Solutions", ""),
    ("freight@myworkday.com", "FedEx Freight Application Status Update",
     "We appreciate your interest in employment opportunities with\nFedEx Freight. This is to notify you that the "
     "company has decided\nto move forward with other candidates", REJECTED, "FedEx Freight", ""),
    ("Syngenta Seeds <notification@careers.syngenta.com>", "Thank you for your application / Gracias por tu postulación",
     "Dear Naman\nWe have received your application for the position of Digital Genomics Prediction Intern "
     "and are currently reviewing your experience and qualifications.", CONFIRMATION, "Syngenta Seeds",
     "Digital Genomics Prediction Intern"),
    ("notify@dayforce.com", "Business Analyst - Pricing & Analytics Application Update",
     "Hello Naman,We have received your application for the position - Business Analyst - Pricing & Analytics "
     "We will be reviewing all applicants shortly. Thank you for giving us the opportunity to consider you for the "
     "Business Analyst - Pricing & Analytics position with OMNIA Partners.", CONFIRMATION, "",
     "Business Analyst - Pricing & Analytics"),
    ("Miles from Avis Budget <careers@avisbudget.com>",
     "Thank You for Applying to the Accelerate - Deployed Transformation Engineer - Post Grad Opportunity Role with Avis Budget Group",
     "Hello Manan, Thank you for applying", CONFIRMATION, "Avis Budget Group", ""),
    ("Citi Human Resources <hr@citi.com>", "Thank you for your interest in Citi!",
     "Dear Manan, Thank you for taking the time to apply for the role of Python Developer", CONFIRMATION, "Citi", "Python Developer"),
    ("no-reply <no-reply@us.greenhouse-mail.io>",
     "We’ve received your application for Software Engineer I, Fullstack (Search) at Affirm",
     "Hi Manan, Thank you for applying", CONFIRMATION, "Affirm", "Software Engineer I, Fullstack (Search)"),
    ("TicketManager <careers@ticketmanager.com>", "Manan, we've received your resume",
     "Manan, Thank you for your interest in joining TicketManager! We've received", CONFIRMATION, "TicketManager", ""),
    ("Abby Care Hiring Team <no-reply@ashbyhq.com>", "We’ve received your application! | Abby Care",
     "Hi Manan, Thank you for your interest in the Applied AI Engineer position", CONFIRMATION, "Abby Care", "Applied AI Engineer"),
    ("Zefr Hiring Team <no-reply@ashbyhq.com>", "Regarding Your Application With ZEFR!",
     "Dear Manan! Thank you so much for your interest in the Software Developer role", CONFIRMATION, "ZEFR", "Software Developer"),
    ("Aurora Hiring Team <no-reply@greenhouse.io>", "Thank you for applying to Aurora",
     "Hi Manan, Thank you for your interest in joining Aurora! We've received your application", CONFIRMATION, "Aurora", ""),
    ("Jobs at Macy’s, Blu <macys@myworkday.com>",
     "Thank You! We received your job application for Macy's 2027 Tech Early Careers - Software Engineer opportunity",
     "", CONFIRMATION, "", ""),
    ("Amex Careers <careers@aexp.com>", "Thank you for applying to AI Engineer III - Enterprise Architecture - 26014856",
     "Hello Manan, Thank you for expressing interest", CONFIRMATION, "Amex", "AI Engineer III - Enterprise Architecture"),
    ("no-reply <no-reply@greenhouse.io>", "Thank you for applying to National Information Solutions Cooperative (NISC)",
     "Hi Manan, Thank you for your interest", CONFIRMATION, "National Information Solutions Cooperative (NISC)", ""),
    ("Amex Careers <careers@aexp.com>", "Please confirm your identity",
     "Hello Manan, Thank you for your interest in working at American Express. Before you", VERIFICATION, "", ""),
    ("Greenhouse <no-reply@greenhouse.io>", "Security code for your application to Affirm",
     "Copy and paste this code into the security code field", VERIFICATION, "", ""),
    ("WorkdaySystemDoNotReply <x@myworkday.com>", "Verify your candidate account",
     "Click this link to confirm your email address", VERIFICATION, "", ""),
    ("NTT DATA AIVista Hiring <jobs@nttdata.com>", "Application Received – NTT DATA AIVista",
     "Hi Manan, Thank you for your interest in NTT DATA AIVista", CONFIRMATION, "NTT DATA AIVista", ""),
    ("SBT Global, Inc. <hr@sbtglobal.com>", "Thank you for applying to SBT Global, Inc.",
     "Dear Manan, Thank you for submitting your application for the position", CONFIRMATION, "SBT Global", ""),
    ("KLA HR <hr@kla.com>", "Thank you for your application!",
     "Manan, Thank you for applying to our Software Engineering Intern position, 26418", CONFIRMATION, "KLA", "Software Engineering Intern"),
    ("salesforce <no-reply@salesforce.com>",
     "Great News! We’ve Received Your Application for the AI Labs Rotational Fellowship, Emerging Talent Position",
     "", CONFIRMATION, "Salesforce", "AI Labs Rotational Fellowship, Emerging Talent"),
    ("no-reply <no-reply@greenhouse.io>", "Thank you for applying to Braze!",
     "Hi Manan, Thank you for your application for the Software Engineer II, User Targeting role", CONFIRMATION, "Braze", ""),
    ("FSH Tech Hiring Team <no-reply@ashbyhq.com>", "Thanks for applying to FSH Technologies!",
     "Hi Manan, Thank you for applying for the Engineer - Intern role at FSH Technologies", CONFIRMATION, "FSH Technologies", "Engineer - Intern"),
    ("Skydio <no-reply@skydio.com>", "Thank you for applying to Skydio!",
     "Hey Manan, Thank you for submitting your application", CONFIRMATION, "Skydio", ""),
    ("no-reply <no-reply@lyft.com>", "Thank you for your application for Software Engineer",
     "Hello Manan, Thank you for your interest in Lyft! We wanted", CONFIRMATION, "Lyft", "Software Engineer"),
    ("no-reply <no-reply@ashbyhq.com>", "Thanks for Your Interest – What’s Next?",
     "Hey Manan, We're excited that you're interested in Levanta and our mission", CONFIRMATION, "Levanta", ""),
    ("ewji.fa.sender <ewji.fa.sender@workflow.email.uk-london-1.ocs.oraclecloud.com>",
     "Thank You for Your Application with eClerx", "Dear Manan", CONFIRMATION, "eClerx", ""),
    ("donotreply_Leidos_HR <donotreply@leidos.com>",
     "Leidos -Thank You For Applying to Software Engineering Professionals - 25k Sign on Bonus",
     "Dear Manan", CONFIRMATION, "Leidos", ""),
    ("Human Resources <hr@ensignservices.net>", "Thanks for Applying to Ensign Services!",
     "Hello Manan, We just received your information for our Junior Software Developer", CONFIRMATION, "Ensign Services", ""),
    ("Tessera Labs Hiring <no-reply@ashbyhq.com>", "We got your application, Manan 🎉",
     "Hi Manan, Thank you for applying for the Full Stack Engineer, Intern role at Tessera Labs", CONFIRMATION, "Tessera Labs", "Full Stack Engineer, Intern"),
    ("Tsenta Inbox <inbox@tsenta.com>", "Thank You for Applying to ServiceNow!",
     "Hi Manan, Thanks for your interest in ServiceNow! We received your application", CONFIRMATION, "ServiceNow", ""),
    ("no-reply <no-reply@greenhouse.io>", "Thank you for applying to CoreWeave",
     "Hi Manan, Thank you for your interest in CoreWeave ! We appreciate", CONFIRMATION, "CoreWeave", ""),
    ("Acme Talent <talent@acme.com>", "Your application to Acme",
     "Hi Manan, thank you for your interest. Unfortunately, we have decided to move forward with other candidates.",
     REJECTED, "Acme", ""),
    ("Acme Talent <talent@acme.com>", "Next steps: schedule an interview with Acme",
     "Hi Manan, we'd like to invite you to interview.", INTERVIEW, "Acme", ""),
    ("Acme <no-reply@hackerrank.com>", "Acme coding assessment",
     "Please complete the HackerRank online assessment within 7 days.", ASSESSMENT, "", ""),
    ("Acme Talent <talent@acme.com>", "Your offer letter from Acme",
     "We are pleased to offer you the position", OFFER, "Acme", ""),
    ("Chetanya <mypersonalmentor-newsletter@mail.beehiiv.com>", "She Landed a $60K Job Offer without applying, But How?",
     "Hello, Before I hand you over to our weekly newsletter... landed an offer letter as a Project Coordinator "
     "without applying for it. The recruiter extended a job offer within 5 days. Register for the free Masterclass.",
     OTHER, "", ""),
    ("Career Coach <coach@careercoach.com>", "Your application strategy is broken",
     "Join our free webinar to learn how to get an offer letter.", OTHER, "", ""),
    ("Modivcare Talent Acquisition <modivcare@myworkday.com>", "Interview - SDET I - Modivcare",
     "Thank you for your interest in our SDET I position! We're excited to invite you to the next stage of the "
     "application process: a 1-hour technical interview. Please share a few dates and times when you're available.",
     INTERVIEW, "Modivcare", ""),
    ("Angana Ray <recruiting@acs.org>", "Application Confirmation",
     "Thank you for applying. We will review your experience and background thoroughly. You will be notified whether "
     "you have been successful in moving to the next stage of the process.", CONFIRMATION, "", ""),
    ("IBM <ibmrecruitment@ibm.com>", "You have successfully submitted your IBM job application - Software Engineer Apprentice",
     "Thank you for applying. While you wait to hear from us, visit our careers page to find tips on acing your interview.", CONFIRMATION, "", ""),
]


class JobEmailTest(unittest.TestCase):
    def test_cases(self):
        for sender, subject, body, kind, company, role in CASES:
            email = Email(id="x", thread_id="x", sender=sender, subject=subject, date="2026-10-19", text=body)
            with self.subTest(subject=subject):
                self.assertEqual(classify(email), kind)
                found = extract(email)
                if company:
                    self.assertEqual(found.company, company)
                if role:
                    self.assertEqual(found.role, role)

    def test_own_reply_is_not_an_application(self):
        email = Email(id="x", thread_id="x", sender="Namz Dwan <me@gmail.com>", subject="Re: Interview - SDET I",
                      date="2026-10-28", text="Thank you for the invitation.", labels=("SENT",))
        self.assertEqual(classify(email), OTHER)


# Raw values the patterns found in real emails, and what they should become.
COMPANIES = [
    ("Navy Federal Credit Union has been received", "Navy Federal Credit Union"),
    ("Daimler Truck and our people inspired", "Daimler Truck"),
    ("Jobs for Humanity itself", "Jobs for Humanity"),
    ("Cytek Biosciences Inc using ADP services", "Cytek Biosciences"),
    ("Welocalize - Application Received", "Welocalize"),
    ("MyWorkday T-Mobile", "T-Mobile"),
    ("ExtensisHR @ icims", "ExtensisHR"),
    ("DAIKIN COMFORT TECHNOLOGIES MFG INC", "Daikin Comfort Technologies"),
    ("You’re in the Game", ""),
    ("Strategy is both rewarding and challenging", "Strategy"),
    ("The", ""),
    ("J.M", "The J.M. Smucker Co."),
    ("Bah", "Booz Allen Hamilton"),
    ("KLA", "KLA"),
    ("Schweitzer Engineering Laboratories", "Schweitzer Engineering Laboratories"),
    ("Hex has been received", "Hex"),
    ("Aon", "Aon"),
    ("Candidate Experience site", ""),
    ("Vestcom has updates", "Vestcom"),
    ("Independent Bank AI Engineer", "Independent Bank"),
    ("Next Steps 🍿", ""),
    ("Applicantemails", ""),
    ("Miami Dolphins and Hard Rock Stadium", "Miami Dolphins and Hard Rock Stadium"),
]
ROLES = [
    ("R-121905 AT&T Technology Development Program was successfully received", "", "AT&T Technology Development Program"),
    ("role. If you are not selected for this", "", ""),
    ("Data Test Analyst I has been received", "", "Data Test Analyst I"),
    ("Sales Reporting & Analysis Intern is currently being reviewed by the hiring team", "", "Sales Reporting & Analysis Intern"),
    ("Junior Ai Prompt Engineer job, you can do it now", "", "Junior Ai Prompt Engineer"),
    ("Software Engineer (Job number: 200063403). We’re glad you’re interested in a career", "", "Software Engineer"),
    ("Software Engineer 1 [2026-12640] position. We aim to connect", "", "Software Engineer 1"),
    ("REQ380441 Summer 2027 Software Engineering Internship", "", "Summer 2027 Software Engineering Internship"),
    ("Snowflake | AI Research Scientist, New Grad", "Snowflake", "AI Research Scientist, New Grad"),
    ("a Analyst - Process Analytics - FCRM 5A", "", "Analyst - Process Analytics - FCRM 5A"),
    ("Intern, Artificial Intelligence &amp; Innovation", "", "Intern, Artificial Intelligence & Innovation"),
    ("this position", "", ""),
    ("Jr. Software QA Engineer", "", "Jr. Software QA Engineer"),
    ("Naman Dewan \u200e- R0173771 Entry Level Software Engineer", "", "Entry Level Software Engineer"),
    ("Kairos Power - Applications Integration Engineer", "Kairos Power", "Applications Integration Engineer"),
    ("Associate Software Engineer II-R00152281", "", "Associate Software Engineer II"),
    ("Business Analyst - Pricing & Analytics", "OMNIA Partners", "Business Analyst - Pricing & Analytics"),
    ("2027 Summer Intern - Enterprise Data Analyst, Data Products (Raleigh, NC)", "",
     "2027 Summer Intern - Enterprise Data Analyst, Data Products"),
]


class TidyTest(unittest.TestCase):
    def test_lowercase_names(self):
        for subject, want in [("Thanks for applying to neurohire.ai", "neurohire.ai"),
                              ("onsemi Your Recent Application-AI Engineer - 2506767", "onsemi"),
                              ("Update on your application", ""),
                              ("Amentum Thanks You for your application", "")]:
            email = Email(id="x", thread_id="x", sender="Workable <noreply@candidates.workablemail.com>",
                          subject=subject, date="2026-10-19", text="")
            with self.subTest(subject=subject):
                self.assertEqual(extract(email).company, want)

    def test_companies(self):
        for raw, want in COMPANIES:
            with self.subTest(raw=raw):
                self.assertEqual(tidy_company(raw), want)

    def test_roles(self):
        for raw, company, want in ROLES:
            with self.subTest(raw=raw):
                self.assertEqual(tidy_role(raw, company), want)

    def test_tsenta_forward_uses_real_sender(self):
        email = Email(id="x", thread_id="x", sender="inbox@mail.tsenta.com", subject="Thanks!", date="2026-10-19",
                      text="We got it.\n\nThis is your Tsenta Managed Email.\nSent From: careers@recruitment.americanexpress.com")
        self.assertEqual(extract(email).company, "Americanexpress")


if __name__ == "__main__":
    unittest.main()
