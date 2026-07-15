import QtQuick

QtObject {
    property string textSize: "standard"
    readonly property real sizeMultiplier: textSize === "extra_large" ? 1.30
                                                : textSize === "large" ? 1.15
                                                : 1.0

    function scaled(value) { return Math.round(value * sizeMultiplier) }

    // Branding stays stable so the accessibility sizes never overrun the
    // fixed-height application header. Content roles scale independently.
    readonly property int brand: 44
    readonly property int pageTitle: scaled(32)
    readonly property int sectionTitle: scaled(23)
    readonly property int cardTitle: scaled(20)
    readonly property int body: scaled(18)
    readonly property int secondaryBody: scaled(16)
    readonly property int button: scaled(17)
    readonly property int status: scaled(16)
    readonly property int resultContent: scaled(19)
    readonly property int caption: scaled(15)
    readonly property int technicalMetadata: scaled(15)

    readonly property real headingLineHeight: 1.12
    readonly property real bodyLineHeight: 1.35
    readonly property real resultLineHeight: 1.42
}
