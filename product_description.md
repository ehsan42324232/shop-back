# Mall Platform - Product Description

## Platform Overview
**Name:** Mall (Persian: فروشگاه‌ساز مال)

Mall is a comprehensive e-commerce platform designed specifically for the Iranian market, operating entirely in Farsi. It enables store owners to build and manage their own online stores through a user-friendly platform.

## Core Features

### Platform Access & Management
- Store owners can log into the platform website to manage their stores
- Products become saleable on their individual websites
- Django admin panel for creating stores, building accounts and managing users
- Manual product creation
- Individual users can create custom products manually

### Product Structure & Attributes
- **Product Class:** Root class with price attribute and image/video lists
- **Tree Levels:** Flexible hierarchy structure
- **Categorization:** Level 1 child attributes can be marked as "categorize by this" to act as subclasses
- **Example:** Clothing as product subclass with:
  - Sex attribute (categorizer) - enables male/female categorization
  - Size attribute (non-categorizer)
- **Predefined Attributes:** Color and description
- **Attribute Presentation:**
  - Color fields: Displayed with corresponding color squares
  - Descriptions: Text boxes

### Product Instances
- Only created from leaf nodes
- **Example Product:** تیشرت یقه گرد نخی (Round Neck Cotton T-shirt)
  - Description: ترکی اصل (Original Turkish)
  - Available in multiple colors (red, yellow) and sizes (XL, XXL)
- **Creation Feature:** Checkbox option to create another instance with identical form data for easier bulk creation
- **Stock Warning:** Alerts customers when only one instance remains

### Social Media Integration
- "Get from social media" button for descriptions, images, and videos
- Retrieves 5 latest posts and stories from Telegram and Instagram
- Separates pictures, videos, and text content
- Users can select materials for product definitions

### Shop Website Features

#### Product Display & Navigation
- Various product lists: recent products, categories, most viewed, recommended
- Complete product and category viewing through menu
- Product search by names and categories
- Advanced filtering by products and attributes at each level
- Sorting options: recent, most viewed, most purchased, price

#### Customization & Themes
- Multiple layout and theme options for shop owners
- Real-time layout and theme changes
- Independent domain options (may or may not be platform subdomain)

#### E-commerce Integration
- Integration with major Iranian logistics providers
- Valid payment gateway connections
- Customer account creation and management
- Order viewing and cart editing
- Checkout functionality
- SMS promotion campaigns

### Authentication & Security
- All platform logins use OTP (One-Time Password) authentication

### Analytics & Dashboard
- Comprehensive dashboards for shop owners
- Sales charts and analytics
- Website view statistics
- Customer interaction metrics

## Design Requirements
- Unique logo design in red, blue, and white colors
- Long, fancy, and modern homepage
- Feature presentations with complementary images and short videos
- Two bold call-to-action buttons (top and middle/bottom)
- Pop-up request forms
- Sliders and online chat functionality
- Login section for store owner admin panel access
- Contact us and about us sections

## Target Market
- Iranian market
- Farsi language interface
- Local logistics and payment provider integration