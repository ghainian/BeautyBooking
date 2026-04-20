using Microsoft.AspNetCore.Mvc;

namespace BeautyBooking.Controllers
{
    public class ThanksController : Controller
    {
        public IActionResult Index()
        {
            return View("thanks");
        }
    }
}
