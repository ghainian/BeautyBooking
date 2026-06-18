using Microsoft.AspNetCore.Localization;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddLocalization();
builder.Services.AddControllersWithViews().AddViewLocalization();

var app = builder.Build();

var supportedCultures = new[] { "da", "en", "fr", "de", "zh" };
var localizationOptions = new RequestLocalizationOptions()
    .SetDefaultCulture("da")
    .AddSupportedCultures(supportedCultures)
    .AddSupportedUICultures(supportedCultures);

localizationOptions.RequestCultureProviders = new IRequestCultureProvider[]
{
    new QueryStringRequestCultureProvider(),
    new CookieRequestCultureProvider(),
    new AcceptLanguageHeaderRequestCultureProvider()
};

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRequestLocalization(localizationOptions);

app.UseRouting();

app.UseAuthorization();

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

app.Run();
