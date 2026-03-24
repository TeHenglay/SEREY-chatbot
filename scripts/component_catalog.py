# Source of truth catalog for all indexable Next.js components.
# Props must match the actual TypeScript prop names exactly.
# Add entries here for every reusable component, then re-run index_components.py.

COMPONENTS = [
    {
        "name": "HeroSection",
        "description": "Full-width hero banner with headline, subheadline, and CTA button. Best for the top of landing pages. Supports dark mode.",
        "props": {
            "title": "string — Main headline text",
            "subtitle": "string — Supporting subheadline text",
            "ctaLabel": "string — Call-to-action button label",
            "ctaHref": "string — Call-to-action button URL",
            "backgroundImage": "string (optional) — URL for background image",
            "darkMode": "boolean (optional) — If true, uses dark color scheme",
        },
        "example": {
            "component": "HeroSection",
            "props": {
                "title": "The Future of Work, Today",
                "subtitle": "Automate everything. Scale effortlessly.",
                "ctaLabel": "Get Started Free",
                "ctaHref": "/signup",
                "darkMode": True,
            },
        },
    },
    {
        "name": "Navbar",
        "description": "Top navigation bar with logo, nav links, and an optional CTA button. Supports sticky positioning.",
        "props": {
            "logo": "string — Text or image URL for the logo",
            "links": "array of { label: string, href: string } — Navigation links",
            "ctaLabel": "string (optional) — Navbar button label",
            "ctaHref": "string (optional) — Navbar button link",
            "sticky": "boolean (optional) — If true, sticks to the top on scroll",
        },
        "example": {
            "component": "Navbar",
            "props": {
                "logo": "MyApp",
                "links": [
                    {"label": "Features", "href": "#features"},
                    {"label": "Pricing", "href": "#pricing"},
                    {"label": "About", "href": "/about"},
                ],
                "ctaLabel": "Start Free Trial",
                "ctaHref": "/signup",
                "sticky": True,
            },
        },
    },
    {
        "name": "FeatureGrid",
        "description": "A responsive grid layout showcasing product features with icons, titles, and descriptions. Ideal for highlighting key benefits.",
        "props": {
            "heading": "string — Section heading text",
            "features": "array of { icon: string, title: string, description: string } — Feature items",
        },
        "example": {
            "component": "FeatureGrid",
            "props": {
                "heading": "Everything You Need",
                "features": [
                    {"icon": "⚡", "title": "Blazing Fast", "description": "Sub-second response times, globally."},
                    {"icon": "🔒", "title": "Secure by Default", "description": "End-to-end encryption on all data."},
                    {"icon": "📊", "title": "Analytics", "description": "Real-time insights into your usage."},
                ],
            },
        },
    },
    {
        "name": "PricingSection",
        "description": "Pricing plans side-by-side with feature lists and CTA buttons per plan. Highlights a recommended plan.",
        "props": {
            "heading": "string — Section heading",
            "plans": "array of { name: string, price: string, features: string[], ctaLabel: string, recommended: boolean } — Pricing plans",
        },
        "example": {
            "component": "PricingSection",
            "props": {
                "heading": "Simple, Transparent Pricing",
                "plans": [
                    {
                        "name": "Starter",
                        "price": "$0/mo",
                        "features": ["5 projects", "1GB storage", "Community support"],
                        "ctaLabel": "Get Started",
                        "recommended": False,
                    },
                    {
                        "name": "Pro",
                        "price": "$29/mo",
                        "features": ["Unlimited projects", "50GB storage", "Priority support", "Custom domain"],
                        "ctaLabel": "Start Free Trial",
                        "recommended": True,
                    },
                ],
            },
        },
    },
    {
        "name": "TestimonialSection",
        "description": "Customer testimonials carousel or grid with quotes, author names, roles, and optional avatars.",
        "props": {
            "heading": "string — Section heading",
            "testimonials": "array of { quote: string, author: string, role: string, avatar: string (optional) } — Testimonial items",
        },
        "example": {
            "component": "TestimonialSection",
            "props": {
                "heading": "Loved by Thousands",
                "testimonials": [
                    {
                        "quote": "This product 10x'd our team's productivity.",
                        "author": "Sarah K.",
                        "role": "CTO at Acme Corp",
                        "avatar": "/avatars/sarah.jpg",
                    },
                    {
                        "quote": "Onboarding took minutes, not weeks.",
                        "author": "James R.",
                        "role": "Founder at LaunchFast",
                        "avatar": "/avatars/james.jpg",
                    },
                ],
            },
        },
    },
    {
        "name": "Footer",
        "description": "Site footer with copyright notice, navigation links, and social media icons.",
        "props": {
            "copyright": "string — Copyright text",
            "links": "array of { label: string, href: string } — Footer navigation links",
            "socialLinks": "array of { platform: string, href: string } — Social media links",
        },
        "example": {
            "component": "Footer",
            "props": {
                "copyright": "© 2025 MyApp. All rights reserved.",
                "links": [
                    {"label": "Privacy", "href": "/privacy"},
                    {"label": "Terms", "href": "/terms"},
                ],
                "socialLinks": [
                    {"platform": "Twitter", "href": "https://twitter.com/myapp"},
                    {"platform": "GitHub", "href": "https://github.com/myapp"},
                ],
            },
        },
    },
]
