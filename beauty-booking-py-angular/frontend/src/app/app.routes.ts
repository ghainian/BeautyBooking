import { Routes } from '@angular/router';
import { HomeComponent } from './pages/home.component';
import { BookComponent } from './pages/book.component';
import { ElevComponent } from './pages/elev.component';
import { ThanksComponent } from './pages/thanks.component';
import { RedirectHomeComponent } from './pages/redirect-home.component';

export const routes: Routes = [
    { path: '', redirectTo: 'home', pathMatch: 'full' },
    { path: 'home', component: HomeComponent },
    { path: 'book/elev', component: ElevComponent },
    { path: 'book', component: BookComponent },
    { path: 'thanks', component: ThanksComponent },
    { path: 'contact', component: RedirectHomeComponent, data: { fragment: 'hours-contact' } },
    { path: 'gallery', component: RedirectHomeComponent, data: { fragment: 'gallery' } },
    { path: 'services', component: RedirectHomeComponent, data: { fragment: 'services' } },
    { path: 'price', component: RedirectHomeComponent, data: { fragment: 'services' } },
    { path: '**', redirectTo: 'home' }
];
