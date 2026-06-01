# Source of truth for all Serey platform knowledge.
# Each entry is one semantic chunk that gets embedded into ChromaDB.
# Add, edit, or remove entries here, then re-run:
#   python scripts/index_serey_knowledge.py

SEREY_KNOWLEDGE = [
    {
        "id": "serey_overview",
        "category": "about",
        "title": "About Serey — Our Story",
        "content": (
            "Serey is a publishing platform built on the belief that every voice deserves a home — free from censorship, owned by its creator. "
            "Build your platform. Own your audience. Tell your story — free from censorship, owned entirely by you.\n\n"
            "What is Serey? "
            "Serey is a publishing platform that lets creators, journalists, and media companies launch customizable websites and online shops with no coding required. "
            "Instead of just building websites, Serey allows you to create fully customizable social publishing platforms — all without the need for technical skills.\n\n"
            "Our Purpose — Digital Sovereignty and Freedom: "
            "Serey was founded with a powerful mission: to bring digital sovereignty and freedom back to the people. "
            "In today's digital landscape, major social media corporations hold vast centralized power, silencing voices, censoring ideas, and shaping public opinion. "
            "Serey was created to counter this control and restore the freedom for people to build social publishing platforms they can fully own and govern. "
            "Censorship Resistant: your content, your rules — no central authority can silence your voice. "
            "Full Ownership: own your platform, your data, and your community. "
            "Global Access: publish freely to audiences anywhere in the world.\n\n"
            "History — Origins: "
            "2018: Serey was born in response to growing concerns over big tech's power to control and suppress information. "
            "Revelations by whistleblowers exposed how centralized platforms could manipulate public opinion. "
            "We recognized blockchain's potential to store and distribute content globally — making censorship nearly impossible and removing centralized points of control. "
            "Today: a fully-featured publishing platform empowering creators worldwide to build spaces for free expression, unbounded by centralized authority. "
            "Founded in 2018. Global platform. Zero coding required. 100% free expression.\n\n"
            "Growth — From Local Beginnings to Global Impact: "
            "What began as a solution for news and blogging in Cambodia quickly grew into a global platform. "
            "Serey shifted from being a localized blog-sharing platform to a decentralized infrastructure, "
            "empowering people worldwide to create their own social publishing platforms. "
            "Today, Serey provides anyone with the tools to build a space for free expression, unbounded by the limitations of centralized authority.\n\n"
            "How to Create Your Own Social Publishing Platform: "
            "Creating a social publishing platform on Serey is simple and intuitive. "
            "Users select from a variety of components — such as a landing page, blog, microblog, fundraising tools, or marketplace — "
            "to build a platform perfectly suited to their community's needs. "
            "This allows each creator to design a space that truly reflects their unique vision and values, free from outside interference or censorship. "
            "Route: /about-us"
        ),
    },
    {
        "id": "serey_marketplace",
        "category": "marketplace",
        "title": "Serey Marketplace",
        "content": (
            "The Serey Marketplace is the central hub where users can browse all products and shops. "
            "The marketplace page is at /sereymarket. "
            "Users can search by category, shop name, or keyword. "
            "Products are organised into clearly defined categories. "
            "Every listing shows the price in both USD and KHR (Cambodian Riel). "
            "Buyers can add items to a cart and check out securely."
        ),
    },
    {
        "id": "serey_categories",
        "category": "marketplace",
        "title": "Product Categories on Serey",
        "content": (
            "Serey organises products into the following categories: "
            "Electronics & Gadgets, Fashion & Clothing (men, women, kids), "
            "Beauty & Personal Care, Home & Living / Furniture, "
            "Food & Beverages (local Cambodian products), Health & Wellness, "
            "Sports & Outdoors, Books & Education, "
            "Handmade & Crafts (artisan goods), Baby & Kids."
        ),
    },
    {
        "id": "serey_shops",
        "category": "shops",
        "title": "Shops on Serey",
        "content": (
            "Shop owners create a storefront page on Serey at /sereymarket/shop. "
            "Each shop has a shop name, logo, and banner image. "
            "Shops display their location (province or city in Cambodia). "
            "Shops list products with photos, descriptions, and prices. "
            "Customers can see a shop's rating and review section. "
            "Buyers can contact sellers via Telegram or phone number."
        ),
    },
    {
        "id": "serey_open_shop",
        "category": "selling",
        "title": "How to Open a Shop on Serey",
        "content": (
            "To open a shop on Serey, you must first ensure your platform has a subscription plan that includes the shop/marketplace feature. "
            "Without an eligible subscription plan, the option to open a shop will not be available. "
            "To buy or upgrade a community subscription plan, visit /social-media-owners (labelled 'Buy a Plan'). "
            "Once you have an eligible plan, follow these steps: "
            "1. Complete your payment setup at /sereymarket/payment-setup. "
            "2. Fill in your shop name, category, and contact info. "
            "3. Upload your first product listing with photos and a price at /sereymarket/myproduct. "
            "4. Your shop goes live immediately after review. "
            "Sellers can manage orders at /sereymarket/myorder."
        ),
    },
    {
        "id": "serey_routes",
        "category": "navigation",
        "title": "Serey Platform Pages and Routes",
        "content": (
            "Key pages and routes on the Serey platform: "
            "/ — Home page. "
            "/feed — Feed page (call it 'Feed', never 'Main Feed'). "
            "/blog — Blog landing page. "
            "/blog/hot — Hot blog posts. "
            "/blog/new — New blog posts. "
            "/blog/trending — Trending blog posts. "
            "/blog/post/new — Create a post. "
            "/blog/post/edit — Edit a post. "
            "/blog/post/draft — Draft posts. "
            "/blog/categories/[[...slug]] — Category/nested pages. "
            "/sereymarket — Main marketplace hub. "
            "/sereymarket/category — Marketplace category page. "
            "/sereymarket/shop — Shop directory. "
            "/sereymarket/product/[product_id] — Product detail page. "
            "/sereymarket/cart — Shopping cart. "
            "/sereymarket/cart/checkout — Checkout flow. "
            "/sereymarket/myorder — Seller order management. "
            "/sereymarket/myorder/userorder — User order history. "
            "/sereymarket/myproduct — Manage product listings. "
            "/sereymarket/payment-setup — Seller payment setup. "
            "/sereymarket/slideshowdashboard — Marketplace dashboard. "
            "/sereymarket/telegram-bot — Marketplace bot integration. "
            "/signup — Account registration. "
            "/reset-password — Password reset flow. "
            "/profile-setting — Profile and account settings. "
            "/my/wallet — User wallet. "
            "/my/notifications — User notifications. "
            "/my/login-devices — Active device and login sessions. "
            "/authors/[name] — Author profile. "
            "/authors/[name]/[permalink] — Author post detail. "
            "/authors/[name]/premium/[permalink] — Premium author post. "
            "/authors/[name]/my-activity — Author activity. "
            "/gallery — Gallery landing page. "
            "/gallery/new — Create gallery content. "
            "/gallery/trending — Trending gallery content. "
            "/gallery/posts — Gallery post listing. "
            "/gallery/following — Gallery following feed. "
            "/gallery/activity — Gallery activity overview. "
            "/gallery/activity/[author] — Gallery activity by author. "
            "/gallery/[author] — Author gallery page. "
            "/gallery/[author]/[photo] — Gallery photo detail. "
            "/drums — Drums landing page. "
            "/drums/feed — Drums feed. "
            "/drums/follow — Followed Drums content. "
            "/drums/notifications — Drums notifications. "
            "/drums/authors/[author] — Drums author page. "
            "/drums/authors/[author]/[permlink] — Drums post detail. "
            "/quiz/category — Quiz category landing. "
            "/quiz/category/[id] — Quiz category detail. "
            "/quiz/category/[id]/view-result — Quiz result view. "
            "/quiz/category/real-exam/[id] — Real exam page. "
            "/quiz/category/test-exam/[id] — Test exam page. "
            "/quiz/start/[id] — Quiz start page. "
            "/quiz/success/[id] — Quiz success page. "
            "/quiz/user/real — User real exam overview. "
            "/quiz/user/real/[id] — User real exam detail. "
            "/quiz/user/test — User test exam overview. "
            "/quiz/user/test/[id] — User test exam detail. "
            "/quiz/admin/category — Quiz admin category page. "
            "/quiz/admin/category/[id] — Quiz admin category detail. "
            "/quiz/admin/question — Quiz admin question page. "
            "/quiz/admin/quiz — Quiz admin quiz page. "
            "/quiz/admin/quiz/[id] — Quiz admin quiz detail. "
            "/quiz/admin/ranking — Quiz admin ranking page. "
            "/quiz/admin/setting — Quiz admin settings. "
            "/social-media-owners — Community manager/owner tools. "
            "/social-media-owners/community-settings — Community settings. "
            "/social-media-owners — Buy a community subscription plan and manage owner tools. "
            "/cambodia — Cambodia community. "
            "/cambodia/serey-ai — Serey AI tools page (this is a page, NOT a community). "
            "/usa — USA community. "
            "/usa/sport — USA sports. "
            "/netherlands — Netherlands community. "
            "/vrij-nederland — Vrij Nederland. "
            "/web3-nederland — Web3 Nederland. "
            "/voetbal — Football landing. "
            "/khmer-ball — Khmer Ball. "
            "/shadow-of-utopia — Shadow of Utopia. "
            "/smartvey — Smartvey landing. "
            "/smartvey/contact-us — Smartvey contact. "
            "/smartvey/condition — Smartvey conditions. "
            "/smartvey/sponsorship — Smartvey sponsorship. "
            "/smartvey/vision-and-goal — Smartvey vision. "
            "/smartvey/who-we-are — Smartvey company info. "
            "/serey-link — Serey Link. "
            "/serey-wallet — Serey Wallet. "
            "/serey-apps — Serey Apps listing page (this is a page, NOT a community). "
            "/pdoge — Pdoge landing. "
            "/pdoge/about-us — Pdoge about. "
            "/pdoge/donate — Pdoge donation. "
            "/video-component — Video platform landing. "
            "/video-component/watch — Video watch page. "
            "/about-us — About Serey. "
            "/faq — Help and support page. "
            "/privacy-policy — Privacy policy. "
            "/term-of-service — Terms of service. "
            "/rules-and-values — Rules and values. "
            "/security-disclosure-program — Security disclosure. "
            "/platform-plan-terms — Platform plan terms. "
            "/founders — Founders. "
            "/alliances — Alliances. "
            "/statistics — Platform statistics. "
            "/kc-university-post — KC University content. "
            "/bookmebus — Book bus, ferry, and train tickets across Cambodia and Southeast Asia. "
            "/cambodian-citizenship-by-investment — Overview and application for the Cambodian Citizenship by Investment program. "
            "/places-to-visit-cambodia — Discover top tourist destinations and attractions in Cambodia. "
            "/cambodia-visa-guide — Comprehensive guide to Cambodian visas, e-visas, and extensions. "
            "/cambodia-payments-guide — Guide to currency (USD/KHR), cash, cards, and mobile payments in Cambodia. "
            "/police-online-reporting — Official portal for reporting scams, fraud, and online crimes in Cambodia. "
            "/cambodia-travel-weather-guide — Practical travel tips and weather information for Cambodia. "
            "/referral-rewards — Referral Rewards Program: earn 20%-25% commission per platform subscription referred. "
            "/creator-ownership-program — Creator Ownership Program: build Serey together, earn phantom equity participation. "
            "/investors — Investor information: Serey's vision, traction, business model, and investment opportunity. "
            "Note: Login is handled through a modal, there is no dedicated login page."
        ),
    },
    {
        "id": "serey_payments",
        "category": "payments",
        "title": "Payment Methods on Serey",
        "content": (
            "Serey supports the following payment methods: "
            "ABA Bank (QR code and online bank transfer), "
            "Wing Money, "
            "Pi Pay, "
            "Cash on Delivery — available in Phnom Penh and major Cambodian cities."
        ),
    },
    {
        "id": "serey_languages",
        "category": "platform",
        "title": "Supported Languages on Serey",
        "content": (
            "Serey supports two languages. "
            "Khmer (ភាសាខ្មែរ) is the primary language of the platform. "
            "English is supported as a secondary language."
        ),
    },
    {
        "id": "serey_support",
        "category": "support",
        "title": "Serey Support and Contact",
        "content": (
            "Users can get help from Serey through the following channels: "
            "FAQ page at /faq. "
            "Email: contact@serey.io. "
            "Telegram: @sereyio"
        ),
    },
    {
        "id": "serey_faq",
        "category": "support",
        "title": "Serey Frequently Asked Questions",
        "content": (
            "General:\n"
            "Q: What is Serey? "
            "A: Serey is a Web3 publishing platform that allows anyone to create their own online platform. "
            "Users can build websites tailored to their audience using tools such as blogs, video pages, galleries, online shops, and more.\n"
            "Q: What is a Superhub? "
            "A: A Superhub is a platform that connects multiple smaller platforms around a shared topic such as Web3, sports, or political news. "
            "It brings content, communities, and platforms together into one ecosystem.\n"
            "Q: Can anyone create a platform on Serey? "
            "A: Yes. Anyone can create their own platform on Serey. You can choose your topic, publish content, grow a community, "
            "and connect your platform to existing Superhubs.\n\n"
            "Platform & Tools:\n"
            "Q: Do I need technical skills to build a platform? "
            "A: No. Serey includes an intuitive CMS and an AI website builder that allow you to create and manage your platform without any technical knowledge.\n"
            "Q: What domain or app options are available? "
            "A: Platforms receive a free subdomain such as platformname.serey.io. "
            "Platforms or Superhubs can also request a dedicated branded mobile app.\n"
            "Q: Who controls the content on each platform? "
            "A: Platform owners control and are responsible for the content they publish. Each platform operates independently within the Serey ecosystem.\n\n"
            "Crypto & Rewards:\n"
            "Q: Does Serey have its own token? "
            "A: Yes. Serey uses the SRY token, which powers the ecosystem and can be used for rewards, governance, and transactions.\n"
            "Q: How can users earn SRY tokens? "
            "A: Users can earn SRY by publishing content, curating posts through voting, and participating actively in the ecosystem.\n"
            "Q: Is it free to post and interact on Serey? "
            "A: Yes. Posting, commenting, and voting on content are completely free.\n\n"
            "Getting Started:\n"
            "Q: How do I get started on Serey? "
            "A: You can create an account, start a platform, publish content, or participate in existing communities — all from the Serey homepage. "
            "Route: /faq"
        ),
    },
    {
        "id": "serey_social_media",
        "category": "social",
        "title": "Serey Communities and Features",
        "content": (
            "Serey has a number of social features, apps, and community hubs: "
            "Blogs: /blog for written content (also /blog/post/new for writing, /authors/[name] for profiles). "
            "Drums: /drums for short-form updates. "
            "Gallery: /gallery for image sharing (also /gallery/[author] for profiles). "
            "Quizzes: /quiz/category for taking and making quizzes (also /quiz/user/real for exams). "
            "Smartvey: /smartvey for Serey's survey and data features. "
            "Video: /video-component for the platform video hub. "
            "Community Pages: Includes /cambodia, /usa, /netherlands, /voetbal, /serey-apps, and others for localized interactions."
        ),
    },
    {
        "id": "bookmebus_info",
        "category": "services",
        "title": "Booking Transport with BookMeBus on Serey",
        "content": (
            "ស្វែងរក និងកក់សំបុត្រឡានក្រុង នាវា រថភ្លើង និងការដឹកជញ្ជូនទៅព្រលានយន្តហោះ ទូទាំងកម្ពុជា និងអាស៊ីអាគ្នេយ៍។ "
            "ប្រៀបធៀបតម្លៃ កាលវិភាគ និងជ្រើសរើសជម្រើសដ៏ល្អបំផុតសម្រាប់ការធ្វើដំណើររបស់អ្នក។\n"
            "ផ្លូវពេញនិយមនៅកម្ពុជា:\n"
            "- ភ្នំពេញ ↔ សៀមរាប: ផ្លូវពេញនិយមបំផុតដែលតភ្ជាប់រាជធានីទៅកាន់អង្គរវត្ត\n"
            "- ភ្នំពេញ ↔ ក្រុងព្រះសីហនុ: ការធ្វើដំណើរទៅកាន់តំបន់ឆ្នេរសមុទ្រនៃកម្ពុជា\n"
            "- សៀមរាប ↔ បាត់ដំបង: រុករកជនបទនៃប្រទេសកម្ពុជា\n"
            "- ភ្នំពេញ ↔ កំពត: ទស្សនាខេត្តដែលល្បីល្បាញខាងម្រេច និងទីក្រុងជាប់មាត់ទន្លេ\n"
            "ហេតុអ្វីត្រូវកក់ជាមួយ BookMeBus?\n"
            "✓ ប្រៀបធៀបប្រតិបត្តិករឡានក្រុង នាវា និងរថភ្លើងជាច្រើននៅកន្លែងតែមួយ\n"
            "✓ ការទូទាត់តាមអ៊ីនធឺណិតប្រកបដោយសុវត្ថិភាព\n"
            "✓ ពិនិត្យមើលកន្លែងទំនេរជាក់ស្តែង និងទទួលបានការបញ្ជាក់ភ្លាមៗ\n"
            "✓ សេវាអតិថិជន 24/7\n"
            "✓ ធានាតម្លៃល្អបំផុត\n"
            "Route: /bookmebus"
        ),
    },
    {
        "id": "hotels_info",
        "category": "services",
        "title": "Finding Hotels and Accommodations in Cambodia",
        "content": (
            "Finding the right place to stay is one of the most important parts of your trip. "
            "Whether you're looking for a luxury resort in Siem Reap, a riverside boutique hotel in Phnom Penh, "
            "or a simple guesthouse by the beach in Sihanoukville, Cambodia has accommodations for every budget and style. "
            "On Serey, we make it easy for you to discover and book trusted hotels across the country. "
            "From family-friendly stays to romantic getaways and backpacker hostels, you'll find options that fit your travel plans. "
            "Browse, compare, and reserve your stay with just a few clicks — so you can focus on enjoying your Cambodian adventure."
        ),
    },
    {
        "id": "places_to_visit",
        "category": "services",
        "title": "Places to Visit in Cambodia",
        "content": (
            "Cambodia is a country rich in history, culture, and natural beauty. "
            "From the ancient temples of Angkor to the bustling streets of Phnom Penh and the pristine beaches of the south, "
            "there are many incredible places to explore.\n\n"
            "Top Destinations:\n"
            "1. Siem Reap: Home to the world-famous Angkor Wat and hundreds of ancient temples.\n"
            "2. Phnom Penh: The vibrant capital city with historical sites like the Royal Palace and National Museum.\n"
            "3. Sihanoukville & Koh Rong: Beautiful coastal areas and tropical islands for relaxation.\n"
            "4. Kampot & Kep: Famous for pepper farms, salt fields, and colonial architecture.\n"
            "5. Battambang: Known for its bamboo train and well-preserved French colonial buildings.\n\n"
            "Route: /places-to-visit-cambodia"
        ),
    },
    {
        "id": "visa_guide",
        "category": "services",
        "title": "Cambodia Visa Guide",
        "content": (
            "Everything you need to know about Cambodian visas, e-visas, and extensions before you pack your bags.\n\n"
            "E-visa Application:\n"
            "The Cambodia e-Visa is the most convenient way for eligible travelers to obtain their entry permit. "
            "The process is entirely online via the Official Government Portal.\n\n"
            "Available Visa Types Online:\n"
            "- Tourist Visa (Visa T): Designed for short visits and holidays (e.g., exploring Angkor Wat).\n"
            "- Ordinary Visa (Visa E): Suitable for long-term stays including work, business, education, or retirement.\n\n"
            "Do you need a visa?\n"
            "Most visitors require a visa. Citizens of ASEAN countries enjoy visa-free entry (14-30 days). "
            "Others must apply in advance, on arrival, or via the e-visa system. Passport must be valid for at least 6 months.\n\n"
            "Common Visa Extensions:\n"
            "1. EB (Business): For expats working or doing business. 1, 3, 6, or 12 months. Requires work permit for employment.\n"
            "2. EG (Job-Seeking): For those seeking employment. Usually granted once.\n"
            "3. ER (Retirement): For retirees aged 55+ with proof of financial support. Multiple-entry.\n"
            "4. ES (Student): For students enrolled in Cambodian schools/universities. Requires proof of enrollment.\n\n"
            "Route: /cambodia-visa-guide"
        ),
    },
    {
        "id": "cambodia_payments",
        "category": "services",
        "title": "Payments in Cambodia Guide",
        "content": (
            "Cambodia uses a mix of US dollars (USD) and Cambodian riel (KHR). Knowing how to handle both is essential.\n\n"
            "Currency Basics:\n"
            "- 1 USD ≈ 4,000 KHR. USD is used for larger purchases; Riel for small daily expenses.\n"
            "- Cash is King: Keep a mix of clean, untorn USD bills and Riel. Damaged USD may be refused.\n\n"
            "Payment Methods:\n"
            "- Mobile Payments: Growing fast via QR codes (ABA, ACLEDA, etc.). Accepted in urban areas.\n"
            "- Cards: Visa/Mastercard accepted at hotels/malls. Small vendors take cash only. 2-3% surcharge may apply.\n"
            "- ATMs: Common in major towns. Charge $4-5 per withdrawal. Usually dispense USD.\n\n"
            "Exchanging Money:\n"
            "- Banks and money changers in markets offer better rates than airports.\n\n"
            "Route: /cambodia-payments-guide"
        ),
    },
    {
        "id": "police_reporting",
        "category": "services",
        "title": "Police Online Reporting in Cambodia",
        "content": (
            "The Cambodian government has introduced an official online reporting system for scams, fraud, and other online crimes.\n\n"
            "Official Police Portal:\n"
            "This system allows citizens and victims to report online crimes directly to the national police "
            "without needing to visit a station in person. It faster and more efficient for sharing information.\n\n"
            "Why it matters:\n"
            "This initiative protects people and prevents fraud. Collaboration between citizens and authorities "
            "improves enforcement and makes Cambodia a safer place for everyone.\n\n"
            "Route: /police-online-reporting"
        ),
    },
    {
        "id": "travel_weather_guide",
        "category": "services",
        "title": "Cambodia Travel & Weather Guide",
        "content": (
            "Cambodia is a warm destination with a tropical climate. Knowing the weather and practical tips ensures a smoother journey.\n\n"
            "Weather & Seasons:\n"
            "- Dry Season (Nov - Apr): Nov-Feb is cool/pleasant (25-30°C), ideal for sightseeing. Mar-Apr is hotter (35°C+) with Khmer New Year.\n"
            "- Wet Season (May - Oct): Expect afternoon showers; lush green landscapes. Mornings are usually dry. Aug-Oct has heaviest rains but fewer crowds.\n\n"
            "Essential Tips:\n"
            "- Best Time to Visit: November to February for comfort.\n"
            "- Cultural Etiquette: Respect local customs; dress modestly at temples.\n"
            "- Health & Safety: Stay hydrated; be aware of common scams in tourist areas.\n"
            "- Connectivity: Local SIM cards are easily available for reliable internet.\n\n"
            "Route: /cambodia-travel-weather-guide"
        ),
    },
    {
        "id": "citizenship_by_investment",
        "category": "services",
        "title": "Cambodian Citizenship by Investment",
        "content": (
            "Cambodia offers a clear and legal pathway for foreign investors to obtain Cambodian citizenship through approved investment programs. "
            "This option is designed for individuals and families seeking long-term stability, greater investment freedom, and a strategic presence in Southeast Asia.\n\n"
            "Program Overview:\n"
            "Applicants may obtain Cambodian citizenship in as little as 12 months. Citizens can directly own land, fully own businesses, "
            "and invest across sectors such as real estate, agriculture, manufacturing, technology, and services. "
            "Citizenship provides access to all ASEAN countries.\n\n"
            "Cambodia prioritizes attracting productive investment and believes it can only become a developed country through technology, "
            "with a strong focus on blockchain, artificial intelligence, and digital innovation.\n\n"
            "This program suits investors and entrepreneurs seeking a second citizenship with flexible residency. "
            "We work with two trusted partners: a specialized law firm and direct coordination with relevant Cambodian government authorities. "
            "Contact us today to explore this opportunity and begin your application.\n\n"
            "Route: /cambodian-citizenship-by-investment"
        ),
    },
    {
        "id": "serey_founder",
        "category": "about",
        "title": "Serey Founder: Chhay Lem Lim",
        "content": (
            "Chhay Lem Lim is the visionary founder of Serey. Initially focused on creating a platform tailored for Cambodia, "
            "Chhay soon recognized Serey's potential to make a global impact. This realization shifted his vision toward "
            "developing Serey into an international platform that empowers communities worldwide. "
            "Chhay plays a hands-on role in collaborating with developers in Cambodia, ensuring that Serey’s growth is grounded "
            "in innovation and teamwork. He is committed to building a revolutionary infrastructure for social publishing platforms, "
            "shaping the future of digital freedom and expression through blockchain technology."
        ),
    },
    {
        "id": "serey_guide_bot_identity",
        "category": "about",
        "title": "Who is Serey guide bot?",
        "content": (
            "Serey guide bot is the official AI assistant of the Serey platform. "
            "It is designed to guide users through the Serey marketplace, "
            "help them find shops, products, and navigate the various features of the platform."
        ),
    },
    {
        "id": "serey_advertising",
        "category": "advertising",
        "title": "Advertise on Serey",
        "content": (
            "Serey is Cambodia's #1 Web3 publishing platform — the most complete Web3 digital publishing platform "
            "where users read, share, and discover every day. "
            "Key audience stats: 12,000+ monthly active users, 43K+ monthly unique visitors, 96K+ page views. "
            "80% Cambodian users with a growing international audience. "
            "Ideal target group: Web3 and fintech savvy users, students, and young professionals. "
            "30 partner platform owners all working together to expand Serey's total userbase. "
            "Ideal for: Tourism & Travel, Hotels & Accommodation, Flights & Transport, Tours & Cruises, "
            "Restaurants & Food, Exclusive Treatments & Wellness.\n\n"
            "Advertising Packages:\n"
            "1. Exclusive Partner (2 spots available): $2,000 (25% discount → $1,500). "
            "Also available: 1 spot at $4,000 (35% discount → $2,600). "
            "Placement: Serey Cambodia main page, Serey.io main page, FEED, under every blog post, Gallery top slider, "
            "and top Market. Mobile app: top Gallery, top Video, top Blog, top Market. "
            "Benefits: Maximum exposure across all key sections, 100% guaranteed visibility as first thing users see, "
            "strong brand presence throughout the user journey.\n\n"
            "2. Premium / Frontpage (2 spots available): $400 per spot (25% discount → $300). "
            "Placement: Serey Cambodia main page and Serey.io main page. "
            "Benefits: 100% guaranteed visibility — first thing users see.\n\n"
            "3. SmartVey Partnership — Student Exposure (2 spots available): $200 per spot. "
            "Placement: Smartvey main page, top Quiz page, top Blog page, top Gallery page. "
            "Benefits: Direct visibility to thousands of active medical students.\n\n"
            "To advertise, contact: contact@serey.io or Telegram: @sereyio"
        ),
    },
    {
        "id": "serey_referral_rewards",
        "category": "earning",
        "title": "Referral Rewards Program — Earn Commission on Serey",
        "content": (
            "Serey's Referral Rewards Program lets you earn extra money while helping Serey grow. "
            "Receive 20%–25% commission on every successful platform subscription you refer. "
            "Earn up to $54 per subscription referral. There is no limit — refer as many people as you want.\n\n"
            "How It Works:\n"
            "1. Share your unique referral link with content creators, businesses, and organizations.\n"
            "2. A new user registers on Serey through your referral link.\n"
            "3. They purchase a Serey platform subscription plan.\n"
            "4. You automatically receive your commission — no extra steps needed.\n\n"
            "Referral Dashboard:\n"
            "Track your referrals, commissions, and earnings through the Referral Dashboard, accessible directly from your account settings. "
            "You can access your unique referral link, monitor referral signups, and follow the growth of your referral network.\n\n"
            "Who Can You Refer?\n"
            "Content creators, influencers, journalists, media companies, sports clubs, businesses, "
            "educational organizations, non-profit organizations, communities, and associations.\n\n"
            "Frequently Asked Questions:\n"
            "Q: When do I receive my commission? "
            "A: Commissions are credited once a referred user successfully purchases a qualifying platform subscription.\n"
            "Q: Is there a limit to how many people I can refer? "
            "A: No. There is no limit to the number of referrals you can make.\n"
            "Q: How can I track my referrals and earnings? "
            "A: Monitor your referral activity, commissions, and earnings through the Referral Dashboard in your account settings.\n"
            "Q: Does it cost anything to participate? "
            "A: No. Joining the Referral Rewards Program is completely free.\n\n"
            "Route: /referral-rewards"
        ),
    },
    {
        "id": "serey_creator_ownership_program",
        "category": "earning",
        "title": "Creator Ownership Program — Build Serey Together",
        "content": (
            "Creators generate billions in value — but capture only a fraction of it. "
            "Large platforms control distribution and take a significant share of revenue, while many creators receive only a small portion of the value they create. "
            "Serey is built to change this: a platform where creators can grow, monetize, and participate in the value they help build.\n\n"
            "What Serey Offers:\n"
            "Serey combines blogs, video, podcasts, online shops, fundraising, communities, and more into one integrated platform. "
            "Creators can build their own publishing platform, grow their audience, and monetize more independently while actively contributing to the growth of the ecosystem. "
            "By joining Serey early, you can: build a direct and independent relationship with your audience; "
            "create multiple revenue streams through advertisement, products, and donations; "
            "grow alongside an emerging ecosystem focused on long-term creator participation; "
            "and benefit from early opportunities within the platform's growth and expansion.\n\n"
            "Who We Target:\n"
            "Undervalued Creators — creators who consistently produce strong content but have not yet reached their full potential. "
            "On most platforms, only a small percentage earn enough to make a living. Serey focuses on these high-quality voices. "
            "Top Creators — we are also open to collaborating with top-tier creators who can help scale the platform and shape its future.\n\n"
            "Focus Sectors (current focus):\n"
            "Science & Education, Homesteading & Sustainability, Liberty & Independent Media, Sports, Tech / AI & Web3, Business & Entrepreneurship, Poker.\n\n"
            "Phantom Equity Participation:\n"
            "To support ecosystem growth, Serey may allocate up to 2% phantom equity participation per sector to selected creators, communities, and strategic contributors — based on long-term contribution, activity, and ecosystem growth. "
            "Selected partners may receive 0.1%–1% growth participation — performance-based, no legal or ownership complexity. "
            "As Serey grows, you benefit from the value you help create.\n\n"
            "Creator Activities:\n"
            "Examples of participation: building a homepage and SereyLink on Serey; using SereyLink to drive traffic and onboard users; "
            "growing activity and audience engagement on their Serey platform; using Serey as a primary publishing hub while complementing with external platforms. "
            "Phantom equity may gradually unlock as creators complete milestones and contribute to ecosystem growth.\n\n"
            "Creator Dashboard:\n"
            "Selected creators get access to a private dashboard showing: your participation agreement with Serey; "
            "your phantom equity participation within the platform; the milestones and steps required to unlock additional participation.\n\n"
            "How to Join:\n"
            "Serey is starting with a select group of creators in this early phase. "
            "Contact Serey at contact@serey.io or Telegram: @sereyio to express interest and explore this together.\n\n"
            "Route: /creator-ownership-program"
        ),
    },
    {
        "id": "serey_investors",
        "category": "about",
        "title": "For Investors — Building the Future of Independent Publishing",
        "content": (
            "Serey is building the infrastructure for the next generation creator economy, "
            "allowing creators and communities to easily launch, monetize, and scale their own independent platforms.\n\n"
            "Overview:\n"
            "Today, a handful of large technology companies capture most of the value created by users and creators "
            "while also controlling what content gets promoted or censored. Serey aims to build a more balanced alternative "
            "by giving creators, communities, and users greater control over their platforms, monetization, and content — "
            "shifting more power and value back to the people who contribute to the ecosystem.\n\n"
            "The Platform:\n"
            "Serey is building an all-in-one publishing ecosystem that enables creators, communities, and media platforms "
            "to launch and grow their own independent platform. Core components: "
            "Publishing tools (blogs, videos, galleries, podcasts, and more); "
            "Monetization (subscriptions, donations, commerce, and advertising); "
            "Independent platforms (customizable homepages and communities); "
            "Growth infrastructure (partnerships, media networks, and distribution). "
            "Unlike traditional platforms that focus on a single channel, Serey combines multiple tools into one integrated ecosystem.\n\n"
            "Traction:\n"
            "10,000+ monthly active users across the platform. "
            "100,000+ monthly page views and growing engagement. "
            "Nearly 30 strategic partners, including B2B Cambodia, Sabay, and Shadows of Utopia. "
            "Increasing creator, publishing, and e-commerce activity across the ecosystem. "
            "Expansion toward international markets through Serey US and Serey Netherlands. "
            "Integrated payment infrastructure supporting Cambodian banks, Visa/Mastercard, and stablecoins such as USDT and USDC.\n\n"
            "Key Partners: SmartVey (Cambodia's largest quiz platform), Digital One (one of Cambodia's largest entertainment companies), "
            "B2B Cambodia (news company focusing on business content).\n\n"
            "Growth Strategy:\n"
            "Current focus: scaling the platform internationally through strategic collaborations, ecosystem expansion, and network-driven growth. "
            "Key areas: collaborating with creators, publishers, media platforms, and online communities to launch and migrate their platforms to Serey; "
            "exploring partnerships with technology platforms such as web browsers, alternative internet ecosystems, and large online communities; "
            "expanding the e-commerce ecosystem through integrated payment systems including domestic bank payments, Visa/Mastercard, and digital assets. "
            "Serey uses referral and partner systems to incentivize creators, businesses, and communities to onboard new users and ecosystems.\n\n"
            "Business Model:\n"
            "Serey generates revenue through platform subscription plans, e-commerce transaction fees, and advertising systems. "
            "Creators, businesses, and communities monetize through subscriptions, online shops, donations, and commercial activity, "
            "while Serey earns revenue by providing the infrastructure and tools that support these ecosystems. "
            "The business model is designed to align platform growth with creator and partner success.\n\n"
            "Company Structure:\n"
            "Serey operates through a US-based LLC, enabling international operations and integration with global payment infrastructure. "
            "Structured to support international growth, partnerships, and future scalability, "
            "with potential plans to transition toward a C Corporation structure as the ecosystem expands.\n\n"
            "Investment Opportunity:\n"
            "Serey is entering a phase focused on international growth and ecosystem expansion. "
            "We are open to discussions with investors and strategic partners who can contribute through capital, networks, strategic guidance, or long-term collaboration. "
            "We look for alignment with our vision around decentralization, digital sovereignty, and more independent online ecosystems, "
            "and the ability to support growth through networks, strategic partnerships, or market access.\n\n"
            "Investor Inquiry: contact@serey.io\n\n"
            "Route: /investors"
        ),
    },
    # -----------------------------------------------------------------------
    # Add more knowledge entries here as Serey grows.
    # Follow the same structure: id, category, title, content.
    # Then re-run: python scripts/index_serey_knowledge.py
    # -----------------------------------------------------------------------
]
