# Source of truth for all Serey platform knowledge.
# Each entry is one semantic chunk that gets embedded into ChromaDB.
# Add, edit, or remove entries here, then re-run:
#   python scripts/index_serey_knowledge.py

SEREY_KNOWLEDGE = [
    {
        "id": "serey_overview",
        "category": "about",
        "title": "What is Serey?",
        "content": (
            "Serey is a Cambodian digital marketplace platform that connects local buyers and sellers online. "
            "The name 'Serey' (សេរី) means 'freedom' in Khmer — representing freedom to buy, sell, and grow. "
            "Serey is built for Cambodian entrepreneurs, small businesses, and individual sellers who want to "
            "reach a wider audience without needing a physical storefront."
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
            "To upgrade or check your subscription plan, visit /social-media-owners/buy-serey-coins. "
            "Once you have an eligible plan, follow these steps: "
            "1. Register or log into your Serey account via the login modal. "
            "2. Complete your payment setup at /sereymarket/payment-setup. "
            "3. Fill in your shop name, category, and contact info. "
            "4. Upload your first product listing with photos and a price at /sereymarket/myproduct. "
            "5. Your shop goes live immediately after review. "
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
            "/feed — Main feed page. "
            "/blog — Blog landing page. "
            "/blog/feed — Blog feed. "
            "/blog/hot — Hot blog posts. "
            "/blog/new — New blog posts. "
            "/blog/trending — Trending blog posts. "
            "/blog/post/new — Create a post. "
            "/blog/post/new-premium — Create a premium post. "
            "/blog/post/edit — Edit a post. "
            "/blog/post/draft — Draft posts. "
            "/blog/categories/[[...slug]] — Category/nested pages. "
            "/blog-premium/new — Premium blog creation. "
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
            "/social-media-owners/buy-serey-coins — Buy Serey coins for owners. "
            "/social-media-owners/temp-buy-coins — Temporary buy coins. "
            "/cambodia — Cambodia community. "
            "/cambodia/serey-ai — Cambodia AI page. "
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
            "/serey-apps — Serey Apps. "
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
            "FAQ at /faq. "
            "Email: contact@serey.io"
            "Telegram: @jokerswild1985"
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
        "id": "soriya_identity",
        "category": "about",
        "title": "Who is Soriya?",
        "content": (
            "Soriya is the official AI assistant of the Serey platform. "
            "She is a helpful Cambodian woman designed to guide users through the Serey marketplace, "
            "help them find shops, products, and navigate the various features of the platform. "
            "Her name, Soriya (សុរិយា), means 'sun' in Khmer, representing warmth and guidance."
        ),
    },
    # -----------------------------------------------------------------------
    # Add more knowledge entries here as Serey grows.
    # Follow the same structure: id, category, title, content.
    # Then re-run: python scripts/index_serey_knowledge.py
    # -----------------------------------------------------------------------
]
