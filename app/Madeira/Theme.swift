import SwiftUI

/// The app's design tokens, in one place.
///
/// Everything visual is derived from here so the whole look can be retuned from
/// this file alone: colours, the background gradient, radii, the spacing scale,
/// type sizes, icon stroke and weight, and the motion timings. Nothing else in
/// the app should hard-code a hex value or a point size.
///
/// The direction is dark, monochrome and calm: white and gray on near-black,
/// one large-radius surface, a single spacing scale, and motion that is felt
/// rather than seen. There is no accent hue anywhere. Emphasis is carried by
/// weight and by white-versus-gray, never by colour, which is why
/// `secondaryText` is a gray of fixed contrast rather than a themed tint.
enum Theme {

    // MARK: - Colour

    /// The app is dark-only by design, not by following the system. A light
    /// theme would need its own token set rather than an inversion: the
    /// backgrounds are near-black with a white glow at the top, and inverting
    /// that produces a look this style does not have.
    enum Palette {
        /// Background gradient, top and bottom.
        static let bgTop = Color(red: 0x2E / 255, green: 0x2E / 255, blue: 0x2E / 255)
        static let bgBottom = Color(red: 0x05 / 255, green: 0x05 / 255, blue: 0x05 / 255)

        /// A card, top and bottom. Deliberately close to the background behind
        /// it so the surface reads as a lift rather than a panel.
        static let surfaceTop = Color(red: 0x26 / 255, green: 0x26 / 255, blue: 0x26 / 255)
        static let surfaceBottom = Color(red: 0x1C / 255, green: 0x1C / 255, blue: 0x1C / 255)

        static let primaryText = Color.white

        /// Values, descriptions, empty states, inactive icons and labels.
        static let secondaryText = Color(red: 0x8E / 255, green: 0x8E / 255, blue: 0x93 / 255)

        /// Hairlines. Two values, not one: a border closes a surface, a divider
        /// only separates rows inside one, and the row separators are inset so
        /// they read as part of the card rather than as its edges.
        static let border = Color.white.opacity(0.08)
        static let divider = Color.white.opacity(0.07)

        /// A filled pill or button.
        static let pillFill = Color.white.opacity(0.12)

        /// Pressed state, a little stronger than the resting fill.
        static let pillFillPressed = Color.white.opacity(0.18)
    }

    /// The screen background. Every root view uses this and ignores the safe
    /// area, so the gradient reaches the physical edges under the status and
    /// home indicators.
    static var background: LinearGradient {
        LinearGradient(colors: [Palette.bgTop, Palette.bgBottom],
                       startPoint: .top, endPoint: .bottom)
    }

    /// A card's own gradient, very slightly lighter at the top-left than the
    /// bottom-right, which is what gives the surface its direction under a flat
    /// fill.
    static var surface: LinearGradient {
        LinearGradient(colors: [Palette.surfaceTop, Palette.surfaceBottom],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    // MARK: - Geometry

    enum Radius {
        /// Cards and grouped containers.
        static let card: CGFloat = 28
        /// Small pill buttons. The upper end of the range reads closer to the
        /// card radius and looks less like a chip.
        static let pill: CGFloat = 20
        /// The smallest pill, for tight controls.
        static let pillSmall: CGFloat = 16
    }

    enum Spacing {
        /// The whole spacing scale. Nothing else should invent a number.
        static let xs: CGFloat = 4
        static let s: CGFloat = 8
        static let m: CGFloat = 12
        static let l: CGFloat = 16
        static let xl: CGFloat = 24
        static let xxl: CGFloat = 32
    }

    enum Layout {
        /// Vertical gap between cards.
        static let cardGap: CGFloat = Spacing.l
        /// Horizontal inset inside a card, left and right.
        static let cardPadding: CGFloat = 20
        /// Row height in a grouped list.
        static let rowHeight: CGFloat = 58
        /// Inset of a row separator from the card's leading and trailing edges,
        /// so it stops short of them.
        static let dividerInset: CGFloat = Spacing.l
        /// Line icons, and the gap from a row icon to its label.
        static let iconSize: CGFloat = 24
        static let iconGap: CGFloat = Spacing.m
        /// Apple's minimum comfortable target.
        static let minTouchTarget: CGFloat = 44
    }

    enum Icon {
        /// Stroke weight for every line icon. Inset symbols keep their own
        /// weight, so a symbolic image set to `unspecified` draws at this.
        static let stroke: CGFloat = 1.9
    }

    // MARK: - Type

    enum Font_ {
        /// Large page titles.
        static let largeTitle = SwiftUI.Font.system(size: 30, weight: .bold, design: .rounded)
        /// List rows.
        static let rowTitle = SwiftUI.Font.system(size: 17, weight: .medium, design: .rounded)
        /// Row values and descriptions.
        static let rowValue = SwiftUI.Font.system(size: 15, weight: .regular, design: .rounded)
        /// Tab labels.
        static let tabLabel = SwiftUI.Font.system(size: 10, weight: .medium, design: .rounded)
        /// Empty states and footnotes.
        static let caption = SwiftUI.Font.system(size: 14, weight: .regular, design: .rounded)
    }

    /// A font configured for a line icon at the app's stroke weight.
    static func icon(_ size: CGFloat = Layout.iconSize) -> SwiftUI.Font {
        .system(size: size, weight: .regular, design: .rounded)
    }

    // MARK: - Motion

    enum Motion {
        /// The press scale. Just enough to feel pressed.
        static let pressScale: CGFloat = 0.97
        /// Standard transition length. Fast enough not to be waited on, slow
        /// enough not to snap.
        static let transition: Double = 0.25
        /// Lighter variant for colour and opacity changes.
        static let quick: Double = 0.2
        static func ease(_ value: Double) -> Animation { .easeInOut(duration: value) }
    }
}

// MARK: - Reusable surfaces

/// A card: the large-radius, subtly graded surface the whole layout is built
/// from. Applied to the container, not to a row.
struct CardBackground: ViewModifier {
    var padding: CGFloat = Theme.Layout.cardPadding

    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(
                RoundedRectangle(cornerRadius: Theme.Radius.card, style: .continuous)
                    .fill(Theme.surface)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.card, style: .continuous)
                    .strokeBorder(Theme.Palette.border, lineWidth: 1)
            )
    }
}

extension View {
    /// Wrap a view in a card. The content decides its own height; this supplies
    /// the surface, the radius, the hairline and the inner padding.
    func card(padding: CGFloat = Theme.Layout.cardPadding) -> some View {
        modifier(CardBackground(padding: padding))
    }

    /// A hairline separator inset from both edges, for rows inside a card.
    func rowDivider() -> some View {
        self
            .padding(.leading, Theme.Layout.dividerInset)
            .padding(.trailing, Theme.Layout.dividerInset)
            .frame(height: 1)
            .background(Theme.Palette.divider)
            .accessibilityHidden(true)
    }

    /// The standard press response: a slight scale and a fade, and nothing else.
    func pressable() -> some View {
        buttonStyle(PressableStyle())
    }
}

struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? Theme.Motion.pressScale : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(Theme.Motion.ease(Theme.Motion.quick), value: configuration.isPressed)
    }
}

// MARK: - Rows

/// One row of a grouped list: a line icon, a white label, an optional gray
/// value on the trailing side and a thin chevron.
///
/// The icon is a symbol rendered with its weight left unspecified so it picks
/// up the system outline, tinted explicitly because an unfilled symbol inherits
/// the label colour rather than staying gray.
struct ListRow: View {
    let systemImage: String
    let title: String
    var value: String?
    var showsChevron: Bool = true

    var body: some View {
        HStack(spacing: Theme.Layout.iconGap) {
            Image(systemName: systemImage)
                .font(Theme.icon())
                .symbolRenderingMode(.monochrome)
                .foregroundStyle(Theme.Palette.secondaryText)
                .frame(width: Theme.Layout.iconSize, height: Theme.Layout.iconSize)

            Text(title)
                .font(Theme.Font_.rowTitle)
                .foregroundStyle(Theme.Palette.primaryText)

            Spacer(minLength: Theme.Spacing.s)

            if let value {
                Text(value)
                    .font(Theme.Font_.rowValue)
                    .foregroundStyle(Theme.Palette.secondaryText)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }

            if showsChevron {
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .symbolRenderingMode(.monochrome)
                    .foregroundStyle(Theme.Palette.secondaryText.opacity(0.7))
            }
        }
        .frame(minHeight: Theme.Layout.rowHeight)
        .contentShape(Rectangle())
    }
}

/// A standalone action, full width, centred: the shape a destructive or
/// terminating row such as Logout takes, so it reads as a command and not as
/// another setting.
struct ActionCard: View {
    let title: String
    var systemImage: String?

    var body: some View {
        HStack(spacing: Theme.Spacing.s) {
            Spacer(minLength: 0)
            if let systemImage {
                Image(systemName: systemImage)
                    .font(Theme.icon(18))
                    .symbolRenderingMode(.monochrome)
                    .foregroundStyle(Theme.Palette.primaryText)
            }
            Text(title)
                .font(Theme.Font_.rowTitle)
                .foregroundStyle(Theme.Palette.primaryText)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, minHeight: Theme.Layout.rowHeight)
        .padding(.horizontal, Theme.Layout.cardPadding)
        .background(
            RoundedRectangle(cornerRadius: Theme.Radius.card, style: .continuous)
                .fill(Theme.surface)
        )
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.card, style: .continuous)
                .strokeBorder(Theme.Palette.border, lineWidth: 1)
        )
    }
}

// MARK: - Buttons

/// A small action: a rounded rectangle with a translucent fill, a line icon and
/// a short label. The app's counterpart to a toolbar item.
struct PillButton: View {
    let title: String
    var systemImage: String?

    var body: some View {
        HStack(spacing: Theme.Spacing.xs + 2) {
            if let systemImage {
                Image(systemName: systemImage)
                    .font(.system(size: 13, weight: .semibold))
                    .symbolRenderingMode(.monochrome)
            }
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .lineLimit(1)
        }
        .foregroundStyle(Theme.Palette.primaryText)
        .padding(.horizontal, Theme.Spacing.m)
        .frame(height: Theme.Layout.minTouchTarget - 8)
        .background(
            RoundedRectangle(cornerRadius: Theme.Radius.pillSmall, style: .continuous)
                .fill(Theme.Palette.pillFill)
        )
    }
}

// MARK: - Screens

extension View {
    /// Put this on a root view. It supplies the gradient behind everything and
    /// extends it under the bars and indicators, so no screen has to remember
    /// to do it.
    func appBackground() -> some View {
        background(Theme.background.ignoresSafeArea())
    }
}

/// A screen title in the header style: large, bold, no background.
struct ScreenTitle: View {
    let text: String

    var body: some View {
        Text(text)
            .font(Theme.Font_.largeTitle)
            .foregroundStyle(Theme.Palette.primaryText)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// An empty state: one gray line icon, one short gray sentence, and the space
/// around them. No illustration, no colour, no second call to action.
struct EmptyStateView: View {
    let systemImage: String
    let message: String

    var body: some View {
        VStack(spacing: Theme.Spacing.m) {
            Image(systemName: systemImage)
                .font(.system(size: 40, weight: .light))
                .symbolRenderingMode(.monochrome)
                .foregroundStyle(Theme.Palette.secondaryText)
            Text(message)
                .font(Theme.Font_.caption)
                .foregroundStyle(Theme.Palette.secondaryText)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, Theme.Spacing.xl)
    }
}

// MARK: - Tab bar

/// A tab's icon. The selected tab is filled and white with a white label; the
/// others are outlined and gray, which is why the two symbols are different
/// rather than one symbol tinted twice.
struct TabIcon: View {
    let outlined: String
    let filled: String
    let isSelected: Bool

    var body: some View {
        Image(systemName: isSelected ? filled : outlined)
            .font(.system(size: 22, weight: .regular))
            .symbolRenderingMode(.monochrome)
            .foregroundStyle(isSelected ? Theme.Palette.primaryText : Theme.Palette.secondaryText)
            .frame(width: Theme.Layout.minTouchTarget, height: 30)
    }
}