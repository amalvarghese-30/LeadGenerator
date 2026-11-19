"""
Script to parse, validate, and queue bulk competitor URLs into LeadIntel crawl jobs.
Supports loading:
  --list research   (53 Research List agencies)
  --list meta       (189 Meta Ads Library entries)
  --list all        (All unique entries)
"""
import sys
import os
import argparse
import asyncio
from urllib.parse import urlparse
from datetime import datetime, timezone
from bson import ObjectId

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.database.connection import connect_to_mongodb, get_database, close_mongodb_connection
from app.utils.job_logger import log_job_event

RESEARCH_LIST = [
    ("DigitalZene", "https://www.digitalzene.com/"),
    ("Personeur", "https://personeur.com/"),
    ("Ra-Aha", "https://ra-aha.com/"),
    ("Bhavik Sarkhedi", "https://bhaviksarkhedi.com/"),
    ("Ohh My Brand", "https://ohhmybrand.com/"),
    ("StartupLy", "https://ashrafmalik.com/entity/startuply/"),
    ("RepuLex", "https://www.repulex.com/"),
    ("BrandYourself", "https://brandyourself.com/"),
    ("Boldface", "https://boldface.online/"),
    ("The People Company", "https://www.thepeoplecompany.me/"),
    ("FableSquare", "https://fablesquare.com/"),
    ("Scribblers India", "https://www.scribblersindia.com/"),
    ("The Influence Forge", "https://www.theinfluenceforge.com/"),
    ("Midas Touch", "https://i-midastouch.com/"),
    ("Moris Media", "https://www.morismedia.in/"),
    ("Brain Box Catalysts", "https://www.brainboxcatalysts.com/"),
    ("Being Blah Blah", "https://www.harshitadagha.in/"),
    ("Digihandler", "https://digihandler.com/"),
    ("RAD Digital", "https://raddigital.in/"),
    ("Postlit Media", "https://postlitmedia.com/"),
    ("The Wise Idiot", "https://thewiseidiot.in/"),
    ("Gliped", "https://gliped.com/"),
    ("BharatCXO", "https://bharatcxo.in/"),
    ("CXO Drive", "https://cxodrive.com/"),
    ("Personal Branding Empire", "https://personalbrandingempire.com/"),
    ("LexiConn", "https://lexiconn.in/"),
    ("ROI Hunt", "https://roihunt.in/"),
    ("Shake Content", "https://shakecontent.com/"),
    ("NPR Design", "https://nprdesign.com/"),
    ("Digital Theory", "https://digitaltheory.co.in/"),
    ("Adfactors PR", "https://www.adfactorspr.com/"),
    ("Edelman India", "https://www.edelman.com/"),
    ("Genesis BCW", "https://www.genesis-bcw.com/"),
    ("RepIndia", "https://www.repindia.com/"),
    ("Concept PR", "https://conceptpr.com/"),
    ("Avian WE", "https://avianwe.com/"),
    ("WATConsult", "https://www.watconsult.com/"),
    ("Techmagnate", "https://www.techmagnate.com/"),
    ("The PRactice", "https://the-practice.net/"),
    ("FNF Media", "https://fnfmedia.in/"),
    ("Schbang", "https://www.schbang.com/"),
    ("YourStory", "https://yourstory.com/"),
    ("Entrepreneur India", "https://www.entrepreneur.com/en-in"),
    ("Forbes India", "https://www.forbesindia.com/"),
    ("The Better India", "https://thebetterindia.com/"),
    ("StartupTalky", "https://startuptalky.com/"),
    ("Inc42", "https://inc42.com/"),
    ("Entrepreneur First", "https://www.joinef.com/"),
    ("FounderTube", "https://foundertube.com/"),
    ("Wikitia", "https://wikitia.com/"),
    ("Crunchbase", "https://www.crunchbase.com/"),
    ("Tracxn", "https://tracxn.com/"),
    ("LinkedIn", "https://www.linkedin.com/"),
]

META_ADS_LIST = [
    ("Sunshy Group Of Companies", "https://go.sunshy.co/opt"),
    ("Lindy Panels", "https://lindypanels.com"),
    ("New York Publications", "http://www.nytpublications.com"),
    ("Simone Sauter", "https://www.skool.com/ai-visibility-lab/about"),
    ("Shapedfy shop", "https://shapedfy.com/products/smart-ai-glasses-sjow"),
    ("Beyer Konoy ApS", "https://beyerkonoy.dk"),
    ("Leadoscrm", "https://myleados.ai/auto-aeo"),
    ("Multiview Inc. (MultiView)", "https://multiviewone.com"),
    ("VisionWeb Ireland", "https://web-rating.com"),
    ("Bangkok Hospital Bangladesh Office", "https://www.lifeandhealthbd.com"),
    ("Leadz Crest", "http://www.leadzcrest.com"),
    ("Ginger Affordable Solutions", "http://www.gingeraffordablesolutions.com"),
    ("Robus Marketing Web Design & Digital Marketing", "https://robusmarketing.com"),
    ("Gloura AI", "https://gloura.org"),
    ("Bloomiro", "https://bloomiro.com"),
    ("Costa Blanca Space", "https://costa-blanca.space/en/costa-blanca-events-calendar-submit-your-event/"),
    ("Try Ninja", "http://tryninja.co"),
    ("GTM Ads", "https://gtmads.com"),
    ("Seoreval", "https://apply.seoreval.com"),
    ("Career Agility System", "https://www.careeragilitysystem.com"),
    ("wecommerce", "https://www.wecommerce.gr"),
    ("3STEPS4WARD A Marketing Company", "https://3steps4ward.com/services/"),
    ("Vodafone Business UK", "https://track.adform.net/C/"),
    ("Nocode.Joshua", "https://www.veed.io/paid-lp/narratives/generic"),
    ("Global Woman Academy", "https://globalwomanevents.com/florence"),
    ("Brad Lea", "https://www.droppingbombs.com/be-my-guest-lander"),
    ("Adobe Express", "https://www.adobeforeducation.com/ambassadors-2025"),
    ("SEEK NZ", "https://nz.employer.seek.com/hiring-advice/article/ways-to-manage-tall-poppy-syndrome-in-your-team"),
    ("The Founder's Dream", "https://thefoundersdream.in/delhi/"),
    ("The Spirits Business", "http://www.join-sip.com/en/node/17464"),
    ("Seb Intel", "https://app.heygen.com/home/business"),
    ("Hashtag Kalakar", "https://www.hashtagkalakar.com/get-featured-in-hashtag-kalakar-magazine"),
    ("Joshhoole", "https://www.skool.com/getpaid/about"),
    ("The Bold Global Awards for Lifetime Achievers & Changemakers", "https://forms.gle/s3Nkf5hP9dfXGKiYA"),
    ("Conviction Marketing Agency", "https://kellyroachinternational.kit.com/liguideads"),
    ("FalkonPodcasts", "https://falkonpodcasts.com/ppc/episode-package-done-for-you-v2/"),
    ("Sina Port", "https://click.brandwithsina.com/brandwithsina"),
    ("Mark Angel", "https://markangelfilmacademy.com"),
    ("Fraser Fontaine & Kong Limited Insurance Brokers", "https://ffkja.com/careers"),
    ("James Smith", "http://www.jamessmith.business/personal-brand-webinar"),
    ("Phil Graham", "https://phil-graham.com/2026-personal-brand/"),
    ("Brand Harvest", "https://brandharvest.io"),
    ("Risen Socials", "http://www.risensocials.com"),
    ("Pooja Marwah", "https://theauthique.com/linkedin-branding-dubai/"),
    ("Pressdia", "https://pressdia.com/uk-offer/"),
    ("Excelerate", "https://experience.4excelerate.org/external/knowMore/Competition/MAGXQ1Z"),
    ("Money.Focus.IG", "https://niklaspedde.com/orange-igu-4-0-sp-no-optinebijdjkf"),
    ("Instytut Praw Migrantów", "https://forms.gle/mhC2fWNp1A59bTWi7"),
    ("Ludify Group Charleston - Real Broker", "https://join.ludifygroup.com/chs-webinar"),
    ("AI Video Bootcamp", "https://www.skool.com/aivideobootcamp/about"),
    ("NP Media Group", "https://niklaspedde.com/orange-igu-4-0-sp-no-optinebijdjkf"),
    ("Mamaariella", "https://www.skool.com/digital-monetisation-academy/about"),
    ("Life's Next Move with Christie and Ken", "http://www.lifesnextmove.com"),
    ("Bień i Pepper", "https://bogatyfotograf.pl/kreator"),
    ("Project THV", "https://unlockthevault.store"),
    ("SmartyMe: High-Value Women Speak", "https://start.smartymeapp.com/quiz"),
    ("Village Wellth", "https://www.villagewellth.com"),
    ("Alfred Nobel Open Business School - Switzerland", "https://anobs.ch/en/application-form/"),
    ("Drkathrynstephenson", "https://go.kathryn-stephenson.co.uk/10-day-email"),
    ("Immerse in earth", "https://www.roadto1million.co"),
    ("SME Centre of Excellence", "https://www.smecofe.com/event-details/social-media-video-workshop-networking-how-to-create-authentic-social-video-that-earns-real-trust"),
    ("Coca-Cola 3E", "https://tinyurl.com/mrnjhrt9"),
    ("Coca-Cola HBC Cyprus", "https://shorturl.at/nQbzB"),
    ("Il Raggio Verde cooperativa sociale", "https://forms.gle/wiKxqNTzpQe2Kdof8"),
    ("Uniwersytet SWPS", "https://openedu.swps.pl/s/swps-product/a0rTt00000hUvjPIAS/"),
    ("Skills and Lead", "https://skillsandlead.pt/curso-de-imagem-pessoal/"),
    ("Wearemarketers", "https://wearemarketers.net/pro/"),
    ("Officine Digitali - Punti Digitale Facile", "https://forms.gle/7Hm3JQZicK9ngy3Z8"),
    ("Iscap P.Porto", "https://shorturl.at/CW2pq"),
    ("Katapedia Digital Branding", "https://katapediabranding.com"),
    ("Job Centre", "https://www.jobcentre.it/annunci/corsi/per-persone-disoccupate/personal-branding-con-linkedin-allapari/"),
    ("Zehufa", "http://miracleesasemesta.com/dewan-2024/"),
    ("Sahabat Caleg", "https://senjamarketing.com/jasa-landingpage-caleg/"),
    ("Frame Indonesia Group", "https://frameindonesiagroup.berdu.pw/digital-campaign"),
    ("politician_academy", "http://bit.ly/7StrategiesPAC"),
    ("VisMin Printing, Packaging & Plastics Show", "http://visminprintpackplas.com/registration"),
    ("McGehrin Group Executive Branding", "https://strategy.mcgehringroup.com"),
    ("CV Suite", "https://cvsuite.co.uk/products/executive-branding"),
    ("vodafonebusinessde", "https://www.vodafone.de/business/blog/podcast/"),
    ("WYY-Rells08", "https://fbweb.cdnovel.com/13621728-fb-187399322-en-core1-iap-1110-core1-iap-video-auto.html"),
    ("Efe Orakpo", "https://tinyurl.com/BMMC02"),
    ("Climbo.com", "https://climbo.com"),
    ("Enjoy-reels-2", "https://fbweb.amolivro.com/13621728-fb-187399322-en-core1-iap-1110-core1-iap-video-auto.html"),
    ("Revive Executive Branding", "https://discover.reviveexecutivebranding.com/executive-resume-service-1"),
    ("Anna Dittrich Branding Fotos", "https://go.annadittrich.com/marketing-women"),
    ("Senses", "https://sensesindia.in/collections/polos"),
    ("Joel Kleber", "https://www.franchisemarketer.co/podcast"),
    ("Bingelabs", "https://bingelabs.in"),
    ("Lever PR", "https://lp.wearelever.it/ebook"),
    ("Branding by Books", "https://www.skool.com/brandingbybooks/about"),
    ("Bobby A. Goodwin", "https://www.skool.com/book/about"),
    ("Mindvalley", "http://www.mindvalley.com/summit/socialmedia"),
    ("Projectsbyaxy", "https://superprofile.bio/bookings/projectsbyaxy"),
    ("Grow Medico", "https://growmedico.in/build-system/"),
    ("Deleteme", "http://deleteme.com"),
    ("Buzz Dealer", "https://buzzdealer.com"),
    ("RK Advertising & Promotion", "https://rkadpro.com"),
    ("Dominate Online", "https://go.dominate.online/offer-3"),
    ("SERPutation", "https://serputation.com"),
    ("Gavilab", "http://www.gavilab.com"),
    ("RepErase", "https://reperase.com"),
    ("Rankingbyseo Inc.", "https://www.rankingbyseo.com/pr-agency-india/"),
    ("Mobile Buzz BD", "http://www.mobilebuzzbd.com/career"),
    ("Semrush Life", "https://careers.semrush.com/jobs/JR100653_Spain/"),
    ("Revuva Australia", "https://revuva.com.au"),
    ("PR Management", "https://prmanagementbd.com/services/personal-reputation-management/"),
    ("The Real Deal", "https://therealdeal.com/sponsored/avantstay/behind-avantstays-ai-powered-disruption-of-the-institutional-hospitality-industry/"),
    ("Mystic Vibes", "https://lsknv.com/1480267b-6720-4d32-b76a-28d93d17f8a9"),
    ("Socinova & Trigacy", "https://socinova.com/pricing/"),
    ("Codebasics", "https://codebasics.io/bootcamps/data-analytics-bootcamp-with-practical-job-assistance/bundle"),
    ("Cozumel Immigration Services", "https://cozumelimmigration.com"),
    ("DaySmart Pet", "https://pet.daysmart.com/book-a-pet-demo/"),
    ("Emerald Coast Connections", "https://members.pcbeach.org/directory/Details/emerald-coast-connections-of-north-florida-3431460"),
    ("Kopava Interactive", "https://kopavainteractive.com"),
    ("one.com", "https://www.one.com/sv/hemsida"),
    ("working out", "https://infinitypublication.online"),
    ("Webinane LLC", "https://themes.webinane.com/lifeline-uk.php"),
    ("Handwriting work", "https://fbinqn.vercel.app"),
    ("BrandBasket", "https://www.brandbasket.in"),
    ("Design.com", "https://www.design.com/s/logo"),
    ("Finderr", "https://sd-22.vercel.app"),
    ("Vihanbhai", "https://candid-faun-1a28dc.netlify.app"),
    ("Handwritten Publisher", "https://guptabhai.github.io/golu/"),
    ("Jim Fisher", "https://moreannuitysales.com/aab"),
    ("name.com", "https://www.name.com/promo/llc"),
    ("Salman Memon", "https://aquamarine-pony-0aac0b.netlify.app"),
    ("BeautyBoss", "https://salonaiagentschatbots.qcmdmarketing.com/beautyboss"),
    ("Bajrang tr", "https://bala-adxo.vercel.app"),
    ("Amherstburg Living - Best Version Media", "https://www.bestversionmedia.com/on/amherstburgliving/advertise/"),
    ("History Village", "https://penultimaconsult.co.uk"),
    ("Digital Marketing", "https://reviewsremoveservice.myshopify.com"),
    ("Kindle Book Publishing", "http://www.kindlesbookpublishing.com"),
    ("Kamal Jahid", "https://storytelling-mastery.com/workshop"),
    ("Jenna Farmer PR", "https://jennafarmerpr.kartra.com/page/parentingmasterclass"),
    ("Rosali Publishing", "https://authoritystackhq.com/Forbesdemo"),
    ("Pipe Rise", "https://go.itsparticle.com/pr/"),
    ("Bond and Vale", "https://apply.bondandvale.com"),
    ("Kindle Direct Publisher", "http://www.kindledirect-publishing.co"),
    ("Differentiate Marketing", "https://differentiatemarketing.com/book"),
    ("Heidi Anderson", "https://www.heidileeanderson.com/offers/KhrzWVmT/checkout"),
    ("ANewswire", "https://anewswire.com"),
    ("Fuel Momentum", "https://fuelmomentum.gumroad.com/l/PR-Blueprint"),
    ("Glam Observer", "https://glamobserver.com/free-webinar"),
    ("Pitch magazine: Stories Of Modern Sport", "https://www.pitch-mag.co.uk/young-sports-journalist-competition"),
    ("Durvesh Yadav", "https://durveshyadav.com/dailyhunt/"),
    ("PressWhizz", "https://presswhizz.com"),
    ("Winsaa Technologies", "https://winsaa.org/biography/"),
    ("SEOClerks", "https://www.seoclerk.com/Link-Building/1056508/300-Powerful-Permanent-DA50-PBNs-SEO-Homepage-Backlinks"),
    ("Minty Digital", "https://www.mintydigital.com/case-studies/digital-pr/spanish-digital-pr/"),
    ("Authority Builders Co.", "https://authority.builders/abc-plus-linkbuilding/"),
    ("ADSY Content Marketing Platform", "http://adsy.com/marketers"),
    ("Domain Coasters", "https://domaincoasters.com/quiz/"),
    ("Click Intelligence Ltd - Link Building Services", "https://app.clickintelligence.co.uk/service/ai-seo-campaign-packages-starter/"),
    ("Suaki", "https://suaki.com/service/100-edu-and-gov-backlinks-for-your-website/"),
    ("AI Automation Experts", "https://go.juliangoldie.com/strategy-session-step2-1303-9119"),
    ("Get Featured", "https://getfeatured.com/special-deal-811592"),
    ("AI Link Boost", "https://optilinkai.com"),
    ("Feedbird", "https://feedbird.com/seo-backlinks"),
    ("Julian Goldie", "https://go.juliangoldie.com/strategy-session-step2-1303-9119-1568"),
    ("Potential Capture", "https://potentialcapturecoach.com/digital-house"),
    ("Nalini Home School", "https://learn.nalinihomeschool.com/web/checkout/6a9af26a5fc862e6f42dbe2f"),
    ("House Creatives PH", "http://housecreatives.com/contentconvention"),
    ("Klixora", "https://klixora.site"),
    ("Vanie Poyey Photography", "https://poyeyphotos.com/3pillars/"),
    ("Ottomanium", "https://www.blaxn.com/casting"),
    ("Skillify Edtech Usa,Uk,Canada", "http://www.skillifytech.com"),
    ("Lil Em’s Custom Cookies", "https://www.gomega.ai/demo"),
    ("Neil Patel", "https://app.neilpatel.com/en/ai-search-visibility"),
    ("WP Engine", "https://wpengine.com/ai-digital-agency-website-strategy-guide"),
    ("Babylovegrowth", "https://babylovegrowth.ai"),
    ("Amrut AI", "https://amrut.ai"),
    ("Squarespace", "https://www.squarespace.com/websites/ai-website-builder"),
    ("Positive Surfer", "https://luma.com/0a6amn0y"),
    ("Ubersuggest", "https://app.neilpatel.com/en/pricing"),
    ("Semrush", "https://www.semrush.com/lp/semrush-one/en/"),
    ("Visigeo", "https://shorturl.at/vRbMC"),
    ("Outrank.so", "https://www.outrank.so"),
    ("JetOctopus", "https://www.searchenginejournal.com/technical-ai-seo-audit-jetoctopus-spa/572262/"),
    ("Perplexity AI", "https://www.perplexity.ai/gen/computer/ai-seo"),
    ("Llumos AI Search Optimization", "https://llumos.app"),
    ("Morrias", "https://morrias.com"),
    ("Move Ahead Media", "https://lin.ee/mGxQErT"),
    ("Kaistone.ai", "https://kaistone.ai"),
    ("TheeDigital", "https://www.theedigital.com/internet-marketing/ai-search-optimization"),
    ("Lead Machine Ventures", "http://leadmachineventures.com/register"),
    ("Peake Management", "http://www.peakemanagement.com"),
    ("Charle", "https://www.charle.co.uk/guides/ai-shopping-guide/"),
]

async def queue_entries(entries, page_limit=50):
    await connect_to_mongodb()
    db = get_database()
    now = datetime.now(timezone.utc)
    queued_count = 0
    skipped_count = 0

    print(f"[*] Processing {len(entries)} competitor targets (page limit: {page_limit})...")

    for name, raw_url in entries:
        raw_url = raw_url.strip()
        if not raw_url:
            continue
        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            clean_url = f"https://{raw_url}"
        else:
            clean_url = raw_url

        try:
            parsed = urlparse(clean_url)
            hostname = (parsed.hostname or "").replace("www.", "").lower()
            if not hostname:
                continue
        except Exception:
            continue

        prov_name = name or hostname.split(".")[0].replace("-", " ").title()

        provider = await db.providers.find_one({
            "$or": [{"domain": hostname}, {"website": clean_url}]
        })
        if not provider:
            prov_doc = {
                "name": prov_name,
                "website": clean_url,
                "domain": hostname,
                "category": "direct_competitor",
                "discovery_status": "researching",
                "created_at": now,
                "updated_at": now,
            }
            res = await db.providers.insert_one(prov_doc)
            prov_id = str(res.inserted_id)
        else:
            prov_id = str(provider["_id"])
            if not provider.get("name") or provider.get("name") == "Unknown":
                await db.providers.update_one({"_id": provider["_id"]}, {"$set": {"name": prov_name}})

        active = await db.crawl_jobs.find_one({
            "provider_id": prov_id,
            "status": {"$in": ["pending", "running"]},
        })
        if active:
            print(f"[-] {prov_name} ({clean_url}) already has active job {active['_id']} ({active.get('status')})")
            skipped_count += 1
            continue

        eff_job_type = "full_research"
        path_l = clean_url.lower()
        if any(seg in path_l for seg in ["/wiki/", "/person/", "/profile/", "/people/", "/author/", "/leadership/", "/executive/"]):
            eff_job_type = "person_profile"

        job_doc = {
            "provider_id": prov_id,
            "provider_name": prov_name,
            "starting_url": clean_url,
            "job_type": eff_job_type,
            "max_pages": page_limit,
            "status": "pending",
            "current_stage": "queued",
            "progress_pct": 0,
            "pages_discovered": 0,
            "pages_attempted": 0,
            "pages_crawled": 0,
            "pages_failed": 0,
            "pages_skipped": 0,
            "pages_analysed": 0,
            "references_found": 0,
            "contacts_created": 0,
            "companies_created": 0,
            "leads_created": 0,
            "errors": [],
            "warnings": [],
            "created_at": now,
            "updated_at": now,
        }
        res_job = await db.crawl_jobs.insert_one(job_doc)
        job_id_str = str(res_job.inserted_id)

        await db.providers.update_one(
            {"_id": ObjectId(prov_id)},
            {"$set": {"discovery_status": "researching", "crawl_job_id": job_id_str}},
        )

        await log_job_event(
            db, job_id_str, "queued", "info", "job_created",
            f"Batch research job queued for {prov_name} ({clean_url})"
        )

        queued_count += 1
        print(f"[+] Queued #{queued_count}: {prov_name} -> Job ID: {job_id_str}")

    print(f"\n[DONE] Queued: {queued_count} jobs | Skipped (already active): {skipped_count}")
    await close_mongodb_connection()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", choices=["research", "meta", "all"], default="research", help="Which list to queue")
    parser.add_argument("--limit", type=int, default=50, help="Page crawl limit per target")
    args = parser.parse_args()

    selected = []
    if args.list == "research":
        selected = RESEARCH_LIST
    elif args.list == "meta":
        selected = META_ADS_LIST
    elif args.list == "all":
        # Deduplicate by domain
        seen_domains = set()
        for n, u in RESEARCH_LIST + META_ADS_LIST:
            try:
                dom = urlparse(u).netloc.replace("www.", "").lower()
                if dom and dom not in seen_domains:
                    seen_domains.add(dom)
                    selected.append((n, u))
            except Exception:
                selected.append((n, u))

    asyncio.run(queue_entries(selected, page_limit=args.limit))
