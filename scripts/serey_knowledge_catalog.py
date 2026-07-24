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
            "Serey is a publishing platform built on the belief that every creator deserves a complete, affordable, and truly owned online presence.\n\n"
            "What is Serey? "
            "Serey is an all-in-one publishing platform that lets creators, journalists, and small businesses build their own website, blog, online shop, "
            "podcast, video channel, community, and more — all in one place, without any technical skills required. "
            "Instead of managing multiple tools like WordPress, Shopify, Substack, and Linktree separately and expensively, "
            "Serey brings everything together in one simple platform that you truly own.\n\n"
            "Our Mission: "
            "Serey was founded with a simple but powerful belief — creators should own their platform, their audience, and their earnings. "
            "Today, most creators depend on platforms that control their reach, take large commissions, and can remove their content or account at any time. "
            "Serey was built to change that by giving every creator the tools to build and grow independently.\n\n"
            "One Platform, Everything You Need: build your website, blog, shop, podcast, community, and more from one simple CMS — no coding or design experience needed. "
            "Affordable and Transparent: stop paying hundreds of dollars managing multiple tools separately; Serey gives you everything at a fraction of the cost with no hidden fees. "
            "Protect Your Work: Serey gives creators the option to timestamp their content, creating a permanent proof of authorship that protects their hard-earned work from plagiarism. "
            "Full Control: customize and manage your platform, content, and community exactly the way you want.\n\n"
            "Our Story: "
            "Serey was founded in 2018 with a simple mission — to give creators a better alternative to the fragmented and expensive tools available at the time. "
            "What started as a small publishing platform has grown into a global platform empowering creators and small businesses worldwide. "
            "Today Serey is growing its creator base across Southeast Asia, Europe, and beyond — with a mission to become the go-to platform for independent creators everywhere. "
            "Serey operates through a registered LLC in the United States, enabling global partnerships and payment integrations. "
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
            "To buy or upgrade a subscription plan, open 'Manage Your Platform' from the top menu, choose the plan that fits you, and click 'Get Started' (route /social-media-owners). "
            "Once you have an eligible plan, follow these steps: "
            "1. Complete your payment setup at /sereymarket/payment-setup. "
            "2. Fill in your shop name, category, and contact info. "
            "3. Upload your first product listing with photos and a price at /sereymarket/myproduct. "
            "4. Your shop goes live immediately after review. "
            "Sellers can manage orders at /sereymarket/myorder."
        ),
    },
    {
        "id": "serey_buy_plan",
        "category": "plans",
        "title": "How to Buy a Serey Plan (Subscription)",
        "content": (
            "To buy a Serey subscription plan for your platform, follow these steps: "
            "1. Open 'Manage Your Platform' from the top menu. "
            "2. Choose the plan that fits you from the plans shown. "
            "3. Click 'Get Started' on that plan. "
            "4. Complete checkout. Serey supports Stripe, Visa, Mastercard, USDT, USDC, and Bakong KHQR. "
            "The plan you pick unlocks features such as the online shop, podcast, video channel, and community tools. "
            "Watch the video tutorial: https://storage.serey.io/videos/01KY9E2T3GDM77W1C9XJNTCF5J.mp4 "
            "Route: /social-media-owners"
        ),
    },
    {
        "id": "serey_routes_core",
        "category": "navigation",
        "title": "Serey Core Navigation — Home, Feed, Blog, Account",
        "content": (
            "Core pages and routes on Serey: "
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
            "/authors/[name] — Author profile. "
            "/authors/[name]/[permalink] — Author post detail. "
            "/authors/[name]/premium/[permalink] — Premium author post. "
            "/authors/[name]/my-activity — Author activity. "
            "/signup — Account registration. "
            "/reset-password — Password reset flow. "
            "/profile-setting — Profile and account settings. "
            "/my/wallet — User wallet. "
            "/my/notifications — User notifications. "
            "/my/login-devices — Active device and login sessions. "
            "/social-media-owners — Community manager/owner tools and subscription plan purchase. "
            "/social-media-owners/community-settings — Community settings. "
            "Note: Login is handled through a modal, there is no dedicated login page."
        ),
    },
    {
        "id": "serey_routes_market",
        "category": "navigation",
        "title": "Serey Marketplace Routes",
        "content": (
            "All Serey Marketplace pages and routes: "
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
            "/sereymarket/telegram-bot — Marketplace Telegram bot integration."
        ),
    },
    {
        "id": "serey_routes_social",
        "category": "navigation",
        "title": "Serey Social Features — Gallery, Drums, Quiz, Smartvey, Video",
        "content": (
            "Social feature pages and routes on Serey: "
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
            "/smartvey — Smartvey landing (survey and data features). "
            "/smartvey/contact-us — Smartvey contact. "
            "/smartvey/condition — Smartvey conditions. "
            "/smartvey/sponsorship — Smartvey sponsorship. "
            "/smartvey/vision-and-goal — Smartvey vision. "
            "/smartvey/who-we-are — Smartvey company info. "
            "/video-component — Video platform landing. "
            "/video-component/watch — Video watch page."
        ),
    },
    {
        "id": "serey_routes_community",
        "category": "navigation",
        "title": "Serey Community Pages",
        "content": (
            "Community and partner pages on Serey. "
            "IMPORTANT: /cambodia/serey-ai and /serey-apps are PAGES, not communities — never suggest them as communities to join. "
            "/cambodia — Cambodia community. "
            "/cambodia/serey-ai — Serey AI tools page (this is a PAGE, NOT a community). "
            "/usa — USA community. "
            "/usa/sport — USA sports community. "
            "/netherlands — Netherlands community. "
            "/vrij-nederland — Vrij Nederland community. "
            "/web3-nederland — Web3 Nederland community. "
            "/voetbal — Football/Voetbal community. "
            "/khmer-ball — Khmer Ball community. "
            "/shadow-of-utopia — Shadow of Utopia community. "
            "/serey-apps — Serey Apps listing page (this is a PAGE, NOT a community). "
            "/serey-link — Serey Link page. "
            "/serey-wallet — Serey Wallet page. "
            "/pdoge — Pdoge landing. "
            "/pdoge/about-us — Pdoge about. "
            "/pdoge/donate — Pdoge donation. "
            "/kc-university-post — KC University content."
        ),
    },
    {
        "id": "serey_routes_info",
        "category": "navigation",
        "title": "Serey Info, Programs, Legal & Cambodia Pages",
        "content": (
            "Informational, program, legal, and Cambodia-related pages on Serey: "
            "/about-us — About Serey. "
            "/faq — Help and support page. "
            "/founders — Founders page. "
            "/alliances — Alliances page. "
            "/statistics — Platform statistics. "
            "/sereyexplorer/explorer — Serey Explorer: browse blockchain-verified posts (proof of authorship and ownership). "
            "/referral-rewards — Referral Rewards Program: earn 20%-25% commission per platform subscription referred. "
            "/creator-ownership-program — Creator Ownership Program: build Serey together, earn phantom equity participation. "
            "/investors — Investor information: Serey's vision, traction, business model, and investment opportunity. "
            "/privacy-policy — Privacy policy. "
            "/term-of-service — Terms of service. "
            "/rules-and-values — Rules and values. "
            "/security-disclosure-program — Security disclosure program. "
            "/report-bug — Report a bug or broken feature. "
            "/platform-plan-terms — Platform plan terms. "
            "/bookmebus — Book bus, ferry, and train tickets across Cambodia and Southeast Asia. "
            "/cambodian-citizenship-by-investment — Overview and application for the Cambodian Citizenship by Investment program. "
            "/places-to-visit-cambodia — Discover top tourist destinations and attractions in Cambodia. "
            "/cambodia-visa-guide — Comprehensive guide to Cambodian visas, e-visas, and extensions. "
            "/cambodia-payments-guide — Guide to currency (USD/KHR), cash, cards, and mobile payments in Cambodia. "
            "/police-online-reporting — Official portal for reporting scams, fraud, and online crimes in Cambodia. "
            "/cambodia-travel-weather-guide — Practical travel tips and weather information for Cambodia."
        ),
    },
    {
        "id": "serey_payments",
        "category": "payments",
        "title": "Payment Methods on Serey",
        "content": (
            "Accept payments from anywhere in the world. "
            "Serey supports multiple payment methods so your audience can support you however they prefer: "
            "credit and debit cards (Visa and Mastercard) through Stripe, "
            "or crypto stablecoin payments received directly to your wallet. "
            "Local Cambodian payment methods are also supported on the marketplace: "
            "ABA Bank (QR code and online bank transfer), Wing Money, Pi Pay, "
            "and Cash on Delivery — available in Phnom Penh and major Cambodian cities."
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
            "Telegram: @sereyio. "
            "Found a bug or broken feature? Report it at /report-bug."
        ),
    },
    {
        "id": "serey_report_bug",
        "category": "support",
        "title": "Report a Bug on Serey",
        "content": (
            "Users can report bugs, errors, or broken features — or share improvement ideas and feedback — "
            "on the Report Bug page at /report-bug (sign-in required). "
            "Describe the issue (for bugs: what you expected, what happened instead, and steps to reproduce), "
            "optionally attach screenshots, and click Send. "
            "Submitted reports can be tracked (open, in progress, resolved), edited, or deleted "
            "in the 'Your reports' section on the same page. "
            "Security vulnerabilities also go through /report-bug — see /security-disclosure-program "
            "for disclosure guidelines and rewards. "
            "Route: /report-bug"
        ),
    },
    {
        "id": "serey_faq",
        "category": "support",
        "title": "Serey Frequently Asked Questions",
        "content": (
            "Everything you need to know about building, growing, and monetizing your platform on Serey.\n\n"
            "General:\n"
            "Q: What is Serey? "
            "A: Serey allows you to create a complete all-in-one platform inexpensively in one place. "
            "Instead of managing multiple platforms like WordPress, Substack, Shopify, Canva, Linktree, and others separately and paying hundreds of dollars, "
            "you get everything you need including a website builder, blog, online shop, community forum, podcast page, video channel, link in bio, and more — "
            "all at a very affordable price.\n\n"
            "Monetization:\n"
            "Q: How can creators make money on Serey? "
            "A: Creators can monetize through multiple channels including selling products in their shop, offering premium content subscriptions, "
            "accepting tips, running paid communities, selling digital products, and earning from banner sponsorships and advertisers — all from one platform.\n"
            "Q: What fees or commission does Serey charge? "
            "A: Serey believes creators should keep as much of what they earn as possible. Serey takes a small commission to support platform development — "
            "less than other platforms. For premium content Serey charges 8.5% including Stripe fees, compared to Substack's 10%. "
            "For online shop sales Serey charges only 1.2%. No hidden fees. Visit the pricing page for full details.\n"
            "Q: Can I sell physical and digital products? "
            "A: Yes. Serey's shop supports both physical and digital products, giving creators and businesses full flexibility to sell whatever they offer, "
            "as long as it is legal in the jurisdiction they operate in. "
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
        "title": "Serey Founder & Partners: Chhay Lem Lim",
        "content": (
            "Our People & Partners — Serey is developed by a focused team and supported by partners across technology, education, and digital platforms.\n\n"
            "Founder — Chhay Lem Lim: "
            "Chhay Lem Lim founded Serey with the vision of creating a complete, affordable, and creator-focused publishing platform. "
            "Recognizing the growing need for independence in the digital world, he focused on building a platform that allows creators and "
            "small businesses to easily build and manage their own online presence — without relying on multiple expensive tools or large technology corporations. "
            "Today his focus is on expanding Serey into a global platform that combines website building, publishing, community, e-commerce, and more in one accessible place. "
            "Chhay works closely with the development team and strategic partners, focusing on product innovation, long-term growth, and international expansion.\n\n"
            "Partners:\n"
            "Paul Frijters — Professor of Wellbeing Economics and former professor at the London School of Economics, who supports Serey's vision "
            "of building fairer and more independent ecosystems for creators and communities.\n"
            "Wallet79 — a Netherlands-based platform connecting employers, job seekers, and educational opportunities. "
            "Serey and Wallet79 collaborate to support creator and business growth across Europe.\n"
            "Open Source Science (OS-Sci) — an initiative providing open source computer science education and training.\n\n"
            "Our Approach: Serey is built as an open and collaborative platform focused on giving creators and small businesses true ownership "
            "and independence online — a complete platform they truly own, fair and transparent monetization, a simple and affordable professional "
            "online presence, tools to protect their work and grow their audience, and a platform that grows alongside its creators and partners. "
            "Route: /founders"
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
    {
        "id": "serey_vision",
        "category": "about",
        "title": "Serey Vision — Your Content, Always Yours",
        "content": (
            "Our Vision: Your content. Always yours. "
            "Most platforms profit from your work — you lose ownership of your content, your audience, and your income. "
            "Serey was built because we believe that's wrong. "
            "We don't just want to host your platform. We want to grow with you — fairer fees, full control, and a genuine partnership, "
            "not a transaction (learn more at the Creator Ownership Program: /creator-ownership-program).\n\n"
            "Blockchain-Verified Ownership: every post you publish gives you the option to store it permanently on the blockchain — "
            "creating undeniable proof of authorship and ownership that no one can take away. "
            "Blockchain-verified posts can be browsed on the Serey Explorer page. Route: /sereyexplorer/explorer\n\n"
            "You Set the Rules: no shadow bans, no reach throttling, no arbitrary takedowns. "
            "Your community, your guidelines, your decisions.\n\n"
            "A Real Partnership: we grow when you grow. "
            "That's why Serey works with selected creators who share the vision and want to build something lasting."
        ),
    },
    {
        "id": "serey_guidelines",
        "category": "platform",
        "title": "Serey Platform Guidelines — Rules and Values",
        "content": (
            "Platform Guidelines define how users and platforms operate within the Serey ecosystem.\n\n"
            "Universal Guidelines (apply to all users and platforms without exception):\n"
            "01. No Theft — unauthorized use or taking of accounts, funds, or content is prohibited.\n"
            "02. No Impersonation or Misrepresentation — users may not falsely represent themselves or others.\n"
            "03. No Fraud or Scams — deceptive practices, including financial scams and phishing, are not allowed.\n"
            "04. No Unauthorized Access — accessing accounts or systems without permission is strictly prohibited.\n"
            "05. Respect Platform Rules and Applicable Laws — users must follow both platform-specific guidelines and relevant laws.\n"
            "06. No Malicious Software — uploading or distributing harmful software or code is not allowed.\n"
            "07. Platform Transparency — platforms must clearly display their terms, policies, and community guidelines.\n\n"
            "Platform-Specific Guidelines: each platform on Serey can define its own content policies and restrictions, "
            "community and interaction rules, monetization models (such as subscriptions or advertising), "
            "and moderation and dispute handling processes. "
            "Platform operators are responsible for clearly communicating and enforcing their rules, "
            "while aligning with Serey's universal guidelines. "
            "Serey provides an open and flexible infrastructure where platforms can operate independently "
            "while maintaining a shared standard of trust, safety, and transparency across the ecosystem. "
            "Route: /rules-and-values"
        ),
    },
    {
        "id": "serey_tutorials",
        "category": "tutorials",
        "title": "Serey Tutorials (Video Guides)",
        "content": (
            "Serey Tutorials is a video guide page that teaches new users how to use the Serey platform "
            "through short, step by step walkthroughs. Several videos include Khmer language narration or subtitles. "
            "The page is at /tutorials and is linked from the site footer under Resources. "
            "The tutorials are grouped into three sections.\n\n"
            "Get Started:\n"
            "1. Buy a Serey Plan. Pick the plan that fits you and check out. Includes Khmer subtitles. "
            "Video: https://storage.serey.io/videos/01KY9E2T3GDM77W1C9XJNTCF5J.mp4\n"
            "2. Set Up Your Serey Link. Build your link in bio so everything sits behind one Serey link. "
            "Video: https://storage.serey.io/videos/01KY9E4N3Q7E5671BEKXBSNF6T.mp4\n\n"
            "Publishing:\n"
            "3. Publish a Blog Post. Publish your first article, from blank draft to live post. "
            "Video: https://storage.serey.io/videos/01KY9E1KDQJ1Z8XYYXSF6HQ32A.mp4\n"
            "4. Post a Podcast. Upload an episode, add details, and publish it to your channel. "
            "Video: https://storage.serey.io/videos/01KY9E35R59CBNFAZ00JEEEH45.mp4\n\n"
            "Grow & Connect:\n"
            "5. Invite Friends & Earn. Share your referral link and earn rewards for every signup. "
            "Video: https://storage.serey.io/videos/01KY9E437A9SZTXA90C4BSNPKQ.mp4\n"
            "6. Add a Group Chat. Turn on group chat so your community can talk in real time. "
            "Video: https://storage.serey.io/videos/01KY9E5BBXVVRY2B3MJNJZHX24.mp4\n\n"
            "Route: /tutorials"
        ),
    },
    # -----------------------------------------------------------------------
    # Add more knowledge entries here as Serey grows.
    # Follow the same structure: id, category, title, content.
    # Then re-run: python scripts/index_serey_knowledge.py
    # -----------------------------------------------------------------------
]

# Contextual prefixes prepended to a chunk's EMBEDDED text only (not the stored content).
# The embedding model (all-MiniLM-L6-v2) truncates input at 256 tokens (~1,000 chars), so any
# chunk longer than that loses its tail at the embedding layer — making tail sub-topics hard to
# find. A short prefix front-loads ALL of the chunk's sub-topics into the first 256 tokens so the
# whole chunk stays findable. The prompt still receives the full original content from metadata.
# Based on Anthropic's Contextual Retrieval technique (Sept 2024).
CONTEXTUAL_PREFIXES: dict[str, str] = {
    "serey_investors": (
        "This chunk describes Serey's investment opportunity for investors and venture partners: "
        "business model and revenue, traction metrics (10,000+ monthly active users, 100,000+ page "
        "views, ~30 partners including B2B Cambodia, Sabay, SmartVey, Digital One), growth strategy, "
        "stablecoin payments (USDT, USDC), company structure (US-based LLC, possible future "
        "C-Corporation), and how to contact the team to invest."
    ),
    "serey_creator_ownership_program": (
        "This chunk describes Serey's Creator Ownership Program: how creators can earn phantom equity "
        "participation (0.1%-1%), the 7 focus sectors, creator activities that unlock milestones, "
        "the private creator dashboard, and how to apply via contact@serey.io."
    ),
    "serey_overview": (
        "This chunk describes what Serey is: an all-in-one publishing platform for websites, blogs, "
        "online shops, podcasts, video channels, and communities; its mission that creators should "
        "own their platform, audience, and earnings; its founding in 2018, affordable transparent "
        "pricing, content timestamping for proof of authorship, growth across Southeast Asia and "
        "Europe, and its registered US LLC."
    ),
    "serey_faq": (
        "This chunk answers frequently asked questions about Serey: what the platform is (all-in-one "
        "alternative to WordPress, Substack, Shopify, Canva, Linktree), how creators monetize (shop, "
        "premium content subscriptions, tips, paid communities, digital products, sponsorships), "
        "Serey's fees and commission (8.5% on premium content vs Substack's 10%, only 1.2% on shop "
        "sales, no hidden fees), and selling physical and digital products."
    ),
    "serey_buy_plan": (
        "This chunk explains how to buy, purchase, get, or upgrade a Serey subscription plan for your "
        "platform: open Manage Your Platform from the top menu, choose the plan that fits you, and click "
        "Get Started, then complete checkout. How do I buy a plan, how to get a Serey plan, where do I "
        "subscribe, how much does a plan cost, upgrade my subscription."
    ),
    "serey_tutorials": (
        "This chunk lists Serey's video tutorials and how to guides on the /tutorials page: how to buy "
        "a Serey plan, how to set up your Serey Link (link in bio), how to publish a blog post, how to "
        "post a podcast, how to invite friends and earn referral rewards, and how to add a group chat. "
        "Where can I learn to use Serey, watch tutorials, video guides, how do I get started, show me a video."
    ),
    "serey_routes_social": (
        "Routes and pages for Serey's social features: watching and uploading videos (video-component), "
        "playing and creating quizzes and exams, browsing and posting to the photo gallery, "
        "drums short-form updates, and smartvey surveys."
    ),
    "serey_routes_info": (
        "Routes for Serey's informational, legal, and program pages: about us, FAQ and help, founders, "
        "alliances, statistics, referral rewards, creator ownership program, investors, privacy policy, "
        "terms of service, and Cambodia travel, visa, payment, and weather guides."
    ),
    "serey_advertising": (
        "This chunk describes advertising and sponsorship options on Serey: exclusive partner spots, "
        "premium frontpage placement, and SmartVey student-exposure packages, with pricing, discounts, "
        "placements, and audience statistics for advertisers."
    ),
    "serey_guide_bot_identity": (
        "This chunk answers who you are and what you can help with: who are you, what are you, what can "
        "you do, what can you help me with, are you a bot, who am I chatting with. You are Serey guide "
        "bot, the official AI assistant for the Serey platform."
    ),
    "serey_support": (
        "This chunk explains how to contact Serey and get help: the support email address "
        "(contact@serey.io), what is your email, how do I reach you, the Telegram channel (@sereyio), "
        "the FAQ help page for customer support, and where to report a bug (/report-bug)."
    ),
    "serey_report_bug": (
        "This chunk explains how to report a bug, error, or broken feature on Serey, or submit an "
        "improvement idea, suggestion, or feedback: I found a bug, something is broken, the page is "
        "not working, where do I report a problem or track my bug report status."
    ),
    "serey_founder": (
        "This chunk answers who founded, created, started, or is behind Serey: the founder of Serey "
        "is Chhay Lem Lim, his vision and focus on global expansion, plus Serey's partners — "
        "Paul Frijters (Wellbeing Economics professor), Wallet79 (Netherlands), and Open Source "
        "Science (OS-Sci). Who is the founder, who created Serey, who made Serey, who started Serey, "
        "who runs Serey, who are Serey's partners and team."
    ),
    "serey_vision": (
        "This chunk describes Serey's vision — your content, always yours: blockchain-verified "
        "ownership where posts can be stored permanently on the blockchain as proof of authorship "
        "(Serey Explorer), no shadow bans or arbitrary takedowns, you set the rules, and a real "
        "partnership where Serey grows with its creators."
    ),
    "serey_guidelines": (
        "This chunk describes Serey's platform guidelines, rules, and values: the seven universal "
        "guidelines (no theft, no impersonation, no fraud or scams, no unauthorized access, respect "
        "laws, no malicious software, platform transparency) and how each platform defines its own "
        "content policies, community rules, monetization, and moderation."
    ),
}
