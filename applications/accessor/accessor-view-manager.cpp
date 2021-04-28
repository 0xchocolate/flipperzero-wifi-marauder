#include "accessor-view-manager.h"
#include "accessor-event.h"
#include <callback-connector.h>

AccessorAppViewManager::AccessorAppViewManager() {
    event_queue = osMessageQueueNew(10, sizeof(AccessorEvent), NULL);

    view_dispatcher = view_dispatcher_alloc();
    auto callback = cbc::obtain_connector(this, &AccessorAppViewManager::previous_view_callback);

    // allocate views
    submenu = submenu_alloc();
    add_view(ViewType::Submenu, submenu_get_view(submenu));

    popup = popup_alloc();
    add_view(ViewType::Popup, popup_get_view(popup));

    gui = static_cast<Gui*>(furi_record_open("gui"));
    view_dispatcher_attach_to_gui(view_dispatcher, gui, ViewDispatcherTypeFullscreen);

    // set previous view callback for all views
    view_set_previous_callback(submenu_get_view(submenu), callback);
    view_set_previous_callback(popup_get_view(popup), callback);
}

AccessorAppViewManager::~AccessorAppViewManager() {
    // remove views
    view_dispatcher_remove_view(
        view_dispatcher, static_cast<uint32_t>(AccessorAppViewManager::ViewType::Submenu));
    view_dispatcher_remove_view(
        view_dispatcher, static_cast<uint32_t>(AccessorAppViewManager::ViewType::Popup));

    // free view modules
    submenu_free(submenu);
    popup_free(popup);

    // free dispatcher
    view_dispatcher_free(view_dispatcher);

    // free event queue
    osMessageQueueDelete(event_queue);
}

void AccessorAppViewManager::switch_to(ViewType type) {
    view_dispatcher_switch_to_view(view_dispatcher, static_cast<uint32_t>(type));
}

Submenu* AccessorAppViewManager::get_submenu() {
    return submenu;
}

Popup* AccessorAppViewManager::get_popup() {
    return popup;
}

void AccessorAppViewManager::receive_event(AccessorEvent* event) {
    if(osMessageQueueGet(event_queue, event, NULL, 100) != osOK) {
        event->type = AccessorEvent::Type::Tick;
    }
}

void AccessorAppViewManager::send_event(AccessorEvent* event) {
    osStatus_t result = osMessageQueuePut(event_queue, event, 0, 0);
    furi_check(result == osOK);
}

uint32_t AccessorAppViewManager::previous_view_callback(void* context) {
    if(event_queue != NULL) {
        AccessorEvent event;
        event.type = AccessorEvent::Type::Back;
        send_event(&event);
    }

    return VIEW_IGNORE;
}

void AccessorAppViewManager::add_view(ViewType view_type, View* view) {
    view_dispatcher_add_view(view_dispatcher, static_cast<uint32_t>(view_type), view);
}