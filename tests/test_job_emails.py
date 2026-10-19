"""Cases taken from real inbox subjects and previews (sender, subject, start of body)."""
import unittest

from tracker.job_emails import (
    ASSESSMENT, CONFIRMATION, INTERVIEW, OFFER, OTHER, REJECTED, VERIFICATION, classify, extract,
)
from tracker.models import Email

# sender, subject, body, kind, company, role ("" = don't check)
CASES = [
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


if __name__ == "__main__":
    unittest.main()
