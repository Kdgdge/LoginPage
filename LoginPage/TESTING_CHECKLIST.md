# OnlyChefs Testing Checklist

## General

- [ ] Site loads and OnlyChefs branding is visible on all pages
- [ ] Navigation bar shows correct links for guests, chefs, and customers

## Authentication

- [ ] Users can sign up as chef or customer
- [ ] Users can log in and log out
- [ ] Flash messages display for login/signup errors and successes

## Chef Features

- [ ] Chefs can log in and see chef dashboard
- [ ] Chefs can add a recipe (with image upload)
- [ ] Chefs can edit a recipe (including changing image)
- [ ] Chefs can delete a recipe
- [ ] Chefs see all their recipes (with images) in Manage Recipes
- [ ] Chefs can edit their profile info (bio)
- [ ] Chefs can view all orders for their recipes
- [ ] Chefs can update order status (pending, accepted, completed, cancelled)

## Customer Features

- [ ] Customers can log in and see customer dashboard
- [ ] Customers can browse the menu (see all recipes with images and chef names)
- [ ] Customers can place an order for a recipe
- [ ] Customers can view their order history (with recipe, chef, status, and time)

## Public Features

- [ ] All users can browse chefs and view chef profiles (bio and recipe list with images)

## Order Status

- [ ] Order status updates by chefs are reflected in customer order history
- [ ] Only chefs can update order status for their own recipes

## Navigation

- [ ] Navigation bar links work and update based on user type
- [ ] Logout returns user to login page and clears session

## File Uploads

- [ ] Recipe images are saved and displayed correctly
- [ ] Only image files are accepted for upload

## Error Handling

- [ ] Accessing restricted pages as the wrong user type shows an error/redirects
- [ ] Invalid form submissions show helpful error messages

---

Check off each item as you test. If you find a bug, note the steps to reproduce and the expected vs. actual behavior.
