using BeautyBooking.Models;
using Microsoft.AspNetCore.Localization;
using Microsoft.AspNetCore.Mvc;
using System.Diagnostics;

namespace BeautyBooking.Controllers
{
    public class ServicesController : Controller
    {
        private readonly ILogger<ServicesController> _logger;

        public ServicesController(ILogger<ServicesController> logger)
        {
            _logger = logger;
        }

        public IActionResult Index()
        {
            var language = HttpContext.Features.Get<IRequestCultureFeature>()?.RequestCulture.UICulture.TwoLetterISOLanguageName ?? "da";
            return Redirect($"/home?culture={language}&ui-culture={language}#services");
        }

        [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
        public IActionResult Error()
        {
            return View(new ErrorViewModel { RequestId = Activity.Current?.Id ?? HttpContext.TraceIdentifier });
        }
    }
}
