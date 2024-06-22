namespace BeautyBooking.Data.Seeding
{
    using System;
    using System.Collections.Generic;
    using System.Linq;
    using System.Threading.Tasks;
    using BeautyBooking.Data.Models;

    public class SalonServicesSeeder : ISeeder
    {
        public async Task SeedAsync(ApplicationDbContext dbContext, IServiceProvider serviceProvider)
        {
            if (dbContext.SalonServices.Any())
            {
                return;
            }

            var salonServices = new List<SalonService>();

            // Fetch salons into a local collection to avoid multiple active readers.
            var salons = dbContext.Salons.ToList();

            foreach (var salon in salons)
            {
                var salonId = salon.Id;
                var categoryId = salon.CategoryId;

                // Fetch services for the current category into a local collection.
                var services = dbContext.Services.Where(x => x.CategoryId == categoryId).ToList();

                foreach (var service in services)
                {
                    var serviceId = service.Id;

                    salonServices.Add(new SalonService
                    {
                        SalonId = salonId,
                        ServiceId = serviceId,
                        Available = true,
                    });
                }
            }
            await dbContext.AddRangeAsync(salonServices);
        }
    }
}
