# Feature Specification: Home Inventory ("My Stuff")

**Feature Branch**: `001-home-inventory`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "A personal, mobile-first web app to catalogue everything I own: photograph an item or paste a product link, have the details filled in for me, browse by room and category, keep receipts, and arrange items together on a visual board."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Photograph an item and have it catalogued (Priority: P1)

Standing in a room holding a phone, the owner opens the app, taps a single prominent "add"
control, and the phone camera opens. They photograph an object. While they wait a moment, the
app inspects the photo and returns to them a form already filled in with a suggested name,
category, brand, and short description. They correct anything wrong, pick the room they are
standing in, optionally add price and purchase date, and save. The item now appears in their
inventory with its photo.

**Why this priority**: This is the whole product. Without it there is no inventory. Every other
story browses or embellishes data that this story creates.

**Independent Test**: Load the app on a phone, photograph three household objects, and confirm
all three are saved with photos and correct details in under a minute each. Delivers a usable
inventory on its own.

**Acceptance Scenarios**:

1. **Given** the owner is on the home screen, **When** they tap the add control and capture a
   photo, **Then** a form appears containing that photo and suggested values for name,
   category, brand, and description.
2. **Given** a form pre-filled with suggestions, **When** the owner edits the name and picks a
   different category, **Then** the saved item stores the owner's values, not the suggestions.
3. **Given** a captured photo, **When** automatic suggestion is unavailable or fails, **Then**
   the form still appears with the photo attached and all fields blank and editable, and the
   item can still be saved.
4. **Given** a completed form, **When** the owner saves, **Then** the item appears in the
   inventory list within two seconds and its photo is visible as a thumbnail.

---

### User Story 2 - Browse and find what has been catalogued (Priority: P1)

The owner wants to look at what they have recorded: a single searchable list of everything, or
narrowed to one room, or narrowed to one category. Tapping any entry shows the full record with
its photo and details, and lets them edit or delete it.

**Why this priority**: Data that cannot be retrieved has no value. Adding and finding together
form the minimum viable product.

**Independent Test**: With a seeded set of items, search by a word in an item name, filter to
"Kitchen", filter to "Electronics", and open, edit, and delete an item.

**Acceptance Scenarios**:

1. **Given** items exist in several rooms, **When** the owner selects the room "Kitchen",
   **Then** only items assigned to Kitchen are listed.
2. **Given** items exist in several categories, **When** the owner selects "Electronics",
   **Then** only items in that category are listed, regardless of room.
3. **Given** the owner types text into search, **When** the text matches part of an item's name,
   brand, or description, **Then** matching items are listed and non-matching ones are not.
4. **Given** an item's detail view, **When** the owner edits a field and saves, **Then** the
   change is reflected in the list.
5. **Given** an item's detail view, **When** the owner deletes the item and confirms, **Then**
   it no longer appears anywhere in the app.

---

### User Story 3 - Add an item from a product link (Priority: P2)

For something bought online, the owner pastes the product page URL into a quick-add field. The
app fetches the product's image and title from that page, shows them for confirmation, and
opens the same form pre-filled so the owner can complete and save the item without ever taking
a photo.

**Why this priority**: A meaningful share of possessions were bought online, and their product
photos are better than anything the owner could shoot. It is additive to, not required by,
stories 1 and 2.

**Independent Test**: Paste a product URL from a retail site and confirm an image and title are
retrieved and the item saves with that image.

**Acceptance Scenarios**:

1. **Given** the quick-add field, **When** the owner pastes a product URL, **Then** the app
   retrieves the page's primary product image and title and displays them for confirmation.
2. **Given** a retrieved image, **When** the owner confirms, **Then** the item form opens
   pre-filled with the title as the name and the image attached, and the source URL is kept
   with the item.
3. **Given** a URL with no retrievable image, **When** retrieval finishes, **Then** the owner is
   told no image was found and is offered the manual form with the URL preserved.

---

### User Story 4 - Keep proof of purchase (Priority: P2)

When the item is a recent purchase, the owner attaches a photo of the receipt, or a link to an
online invoice, alongside the item, and records what it cost, when it was bought, and — for
valuables — its serial number.

**Why this priority**: This is what makes the inventory useful for insurance or warranty
claims, but the inventory is still useful without it.

**Independent Test**: Attach a receipt photo to an existing item, record price, date, and
serial number, reopen the item, and confirm the receipt is viewable.

**Acceptance Scenarios**:

1. **Given** the item form, **When** the owner attaches a receipt photo, **Then** the receipt is
   stored with the item and is viewable separately from the item photo.
2. **Given** the item form, **When** the owner enters a purchase price and date, **Then** those
   values are stored and displayed on the item's detail view.
3. **Given** an item with no receipt, **When** it is viewed, **Then** no receipt area is shown
   and nothing appears broken.

---

### User Story 5 - Browse visually and arrange items together (Priority: P3)

The owner opens a gallery of photos only — no text — and scrolls through their possessions
visually, tapping any photo to see its details. From a board view, they pull items out of a
sidebar onto a free-form canvas, move, resize, and stack them to plan an outfit or picture how
furniture would sit together, then name and save the board to return to later.

**Why this priority**: This turns a database into something enjoyable to use, but it depends
entirely on there being a well-populated inventory first.

**Independent Test**: With items catalogued, scroll the gallery, then create a board, drag four
items onto it, rearrange them, save, reload the page, and confirm the arrangement is unchanged.

**Acceptance Scenarios**:

1. **Given** items with photos, **When** the owner opens the gallery, **Then** photos are shown
   in a grid with no text, and tapping one opens that item's details.
2. **Given** a new board, **When** the owner drags an item from the sidebar onto the canvas,
   **Then** the item's photo appears at the drop position.
3. **Given** items on a board, **When** the owner moves, resizes, or restacks them and saves,
   **Then** reloading the board restores the same positions, sizes, and stacking order.
4. **Given** a saved board, **When** the owner removes an item from the board, **Then** the item
   remains in the inventory and only its placement on the board is removed.

---

### User Story 6 - Keep the inventory private (Priority: P1)

The app is reachable at a public web address, so before seeing or changing anything the owner
must enter a password. Once entered, the session lasts long enough that they are not asked
again during normal use.

**Why this priority**: The inventory is a catalogue of a home's contents; it must not be
readable by anyone who finds the address. It must ship with the first release.

**Independent Test**: Visit the app in a fresh browser session, confirm data is inaccessible
until the password is given, and confirm the session persists across page reloads.

**Acceptance Scenarios**:

1. **Given** a browser with no session, **When** any page or item data is requested, **Then**
   the owner is shown a password prompt and no inventory data is returned.
2. **Given** the correct password, **When** it is submitted, **Then** the owner reaches the
   inventory and remains signed in across page reloads and app restarts for at least 30 days.
3. **Given** an incorrect password, **When** it is submitted, **Then** access is refused and no
   detail is given about why.

---

### Edge Cases

- A photo is captured but the network drops before upload completes: the owner is told the save
  failed and the form retains everything they typed so they can retry.
- Automatic suggestion returns a category that is not one of the known categories: the value is
  discarded and the category field is left for the owner to pick.
- A pasted link points to a page that is slow, requires login, or blocks automated fetching:
  retrieval gives up within a few seconds and offers the manual form.
- A photo is very large (a modern phone photo of 5–15 MB): it is accepted, and browsing screens
  do not download full-size originals.
- The owner assigns an item to a room, then wants a room that does not exist: rooms and
  categories can be added and renamed by the owner.
- An item is deleted while it sits on a board: it disappears from the board too, and the board
  still opens.
- Two devices are used at once: the last save wins, and neither device shows a corrupted record.

## Requirements *(mandatory)*

### Functional Requirements

**Capture and creation**

- **FR-001**: The system MUST let the owner start a new item either by capturing a photo with
  the device camera, by choosing an existing image, or by pasting a product URL.
- **FR-002**: The system MUST, on receiving an item photo, produce suggested values for name,
  category, brand, and a short description, and present them in an editable form.
- **FR-003**: The system MUST clearly mark suggested values as suggestions and MUST allow every
  one of them to be changed or cleared before saving.
- **FR-004**: The system MUST allow an item to be saved when suggestion fails, is unavailable,
  or is rejected by the owner.
- **FR-005**: The system MUST, on receiving a product URL, retrieve that page's primary image
  and title, present them for confirmation, and store the URL with the resulting item.
- **FR-006**: The system MUST abandon link retrieval and offer the manual form if the page does
  not respond within a short, fixed time limit.

**Item record**

- **FR-007**: The system MUST store for each item: a name, a room, a category, and a photo.
- **FR-008**: The system MUST optionally store for each item: brand, purchase price, purchase
  date, serial number, free-text notes, a source URL, and a receipt image.
- **FR-009**: The system MUST require a name and MUST allow every other field except the
  identifier to be empty.
- **FR-010**: The system MUST let the owner edit any field of an existing item and delete an
  item, with deletion requiring a confirmation.

**Organisation and retrieval**

- **FR-011**: The system MUST provide a single list of all items showing a thumbnail and name.
- **FR-012**: The system MUST let the owner filter items by room and by category, and combine
  filters with search.
- **FR-013**: The system MUST provide text search matching against name, brand, and notes.
- **FR-014**: The system MUST ship with the rooms Kitchen, Bedroom, Lounge, Bathroom, and
  Storage Room, and the categories Furniture, Electronics, Major Appliances, Small Appliances,
  Kitchenware, Tools, Decor, Clothing & Accessories, and Miscellaneous.
- **FR-015**: The system MUST let the owner add, rename, and remove rooms and categories; a
  room or category still in use MUST NOT be removable until its items are reassigned.

**Gallery and boards**

- **FR-016**: The system MUST provide a photo-only gallery view of all items, where selecting a
  photo opens that item's details.
- **FR-017**: The system MUST let the owner create named boards, place items from their
  inventory onto a board, and reposition, resize, and restack them.
- **FR-018**: The system MUST persist each placement's position, size, and stacking order, and
  MUST restore them exactly when the board is reopened.
- **FR-019**: Placing an item on a board, or removing it from one, MUST NOT alter the item
  itself; deleting an item MUST remove its placements.

**Access**

- **FR-020**: The system MUST refuse all inventory reads and writes to a visitor who has not
  supplied the correct password.
- **FR-021**: A successful sign-in MUST persist for at least 30 days across page reloads and
  server restarts, and the owner MUST be able to sign out.

**Media handling**

- **FR-022**: The system MUST accept photos of at least 15 MB from a phone camera.
- **FR-023**: Listing and gallery views MUST NOT require downloading full-size originals.
- **FR-024**: Stored photos and receipts MUST NOT be readable by anyone who has not signed in.

### Key Entities

- **Item**: One possession. Carries its name, optional brand, optional purchase price and date,
  optional serial number, optional notes, optional source URL, its photo, an optional receipt
  image, and belongs to exactly one room and one category.
- **Room**: A place in the home an item lives in. Has a name; several are pre-seeded and the
  owner may manage the list.
- **Category**: What kind of thing an item is, independent of where it lives. Has a name;
  several are pre-seeded and the owner may manage the list.
- **Board**: A named visual arrangement — an outfit, a room plan. Has a name and a creation
  time, and holds any number of placements.
- **Placement**: One item's appearance on one board, carrying its position, size, and stacking
  order. Belongs to exactly one board and refers to exactly one item.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The owner can add an item, from opening the app to a saved record, in under 30
  seconds on a phone over a normal mobile connection.
- **SC-002**: Suggested details are accepted without correction for at least 70% of clearly
  photographed household items — that is, the owner usually edits nothing but the room.
- **SC-003**: Suggestions appear within 5 seconds of the photo being captured, 9 times out of 10.
- **SC-004**: Any catalogued item can be found again in under 15 seconds using search or a room
  or category filter.
- **SC-005**: A board with 10 items reopens with every item in exactly the position, size, and
  stacking order it was left in.
- **SC-006**: With 500 items catalogued, list and gallery views become usable within 3 seconds
  of opening.
- **SC-007**: Running cost is under 2 USD per month for a single owner cataloguing up to 1000
  items, and approaches zero in months with no use.
- **SC-008**: No inventory data or image is retrievable by an unauthenticated visitor.

## Assumptions

- Exactly one person uses the app, on their own phone and laptop; there are no accounts, no
  sharing, and no permissions model.
- The owner is always online when using the app; offline capture and later sync are out of
  scope.
- The inventory holds hundreds to low thousands of items, not tens of thousands.
- Suggested item details are a convenience, not a source of truth; the owner is the authority
  on their possessions and always gets the last edit.
- One item has one photo. Multiple photos per item are out of scope for this release.
- Product pages are fetched only when the owner explicitly pastes a link; the app does not
  crawl, log in to, or bypass protections on any site.
- Barcode scanning, depreciation calculations, insurance-claim exports, and multi-user access
  are out of scope, per the original brief.
