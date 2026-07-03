using BeautyBooking.Localization;

namespace BeautyBooking.Tests;

public class SiteTextTests
{
    [Fact]
    public void EverySupportedLanguage_ContainsAllKnownKeys()
    {
        var languages = SiteText.GetSupportedLanguages();
        var keys = SiteText.GetKnownKeys();

        foreach (var language in languages)
        {
            foreach (var key in keys)
            {
                var value = SiteText.Get(key, language);

                Assert.False(string.IsNullOrWhiteSpace(value));
            }
        }
    }

    [Fact]
    public void UnknownLanguage_FallsBackToDanish()
    {
        var keys = SiteText.GetKnownKeys();

        foreach (var key in keys)
        {
            Assert.Equal(SiteText.Get(key, "da"), SiteText.Get(key, "xx"));
        }
    }

    [Fact]
    public void DanishNavigationAndServiceLabels_AreTranslatedCorrectly()
    {
        Assert.Equal("Hjem", SiteText.Get("NavHome", "da"));
        Assert.Equal("Behandlinger", SiteText.Get("NavServices", "da"));
        Assert.Equal("Vores behandlinger", SiteText.Get("ServicesEyebrow", "da"));
        Assert.Equal("Gå til booking", SiteText.Get("FooterGoBooking", "da"));
    }
}
