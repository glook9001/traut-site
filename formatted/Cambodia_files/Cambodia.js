// Created by iWeb 3.0.4 local-build-20130428

function createMediaStream_id2() {
  return IWCreatePhotocast("Cambodia_files/rss.xml", true);
}
function initializeMediaStream_id2() {
  createMediaStream_id2().load("", function(imageStream) {
    var entryCount = imageStream.length;
    var headerView = widgets["widget1"];
    headerView.setPreferenceForKey(imageStream.length, "entryCount");
    NotificationCenter.postNotification(new IWNotification("SetPage", "id2", { pageIndex: 0 }));
  });
}
function layoutMediaGrid_id2(range) {
  createMediaStream_id2().load("", function(imageStream) {
    if (range == null) {
      range = new IWRange(0, imageStream.length);
    }
    IWLayoutPhotoGrid("id2", new IWPhotoGridLayout(4, new IWSize(149, 149), new IWSize(149, 28), new IWSize(162, 192), 27, 27, 0, new IWSize(19, 19)), new IWPhotoFrame([IWCreateImage("Cambodia_files/Watercolor_iweb_01.png"), IWCreateImage("Cambodia_files/Watercolor_iweb_02.png"), IWCreateImage("Cambodia_files/Watercolor_iweb_04.png"), IWCreateImage("Cambodia_files/Watercolor_iweb_08.png"), IWCreateImage("Cambodia_files/Watercolor_iweb_16.png"), IWCreateImage("Cambodia_files/Watercolor_iweb_14.png"), IWCreateImage("Cambodia_files/Watercolor_iweb_13.png"), IWCreateImage("Cambodia_files/Watercolor_iweb_05.png")], null, 0, 0.8, 0, 0, 0, 0, 12, 12, 11, 11, 13, 12, 13, 12, null, null, null, 0.5), imageStream, range, null, null, 1, { backgroundColor: "rgb(0, 0, 0)", reflectionHeight: 0, reflectionOffset: 2, captionHeight: 100, fullScreen: 1, transitionIndex: 2 }, "Media/slideshow.html", "widget1", "widget2", "widget3");
  });
}
function relayoutMediaGrid_id2(notification) {
  var userInfo = notification.userInfo();
  var range = userInfo["range"];
  layoutMediaGrid_id2(range);
}
function onStubPage() {
  var args = window.location.href.toQueryParams();
  parent.IWMediaStreamPhotoPageSetMediaStream(createMediaStream_id2(), args.id);
}
if (window.stubPage) {
  onStubPage();
}
setTransparentGifURL("Media/transparent.gif");
function hostedOnDM() {
  return false;
}
function onPageLoad() {
  IWRegisterNamedImage("comment overlay", "Media/Photo-Overlay-Comment.png");
  IWRegisterNamedImage("movie overlay", "Media/Photo-Overlay-Movie.png");
  loadMozillaCSS("Cambodia_files/CambodiaMoz.css");
  adjustLineHeightIfTooBig("id1");
  adjustFontSizeIfTooBig("id1");
  NotificationCenter.addObserver(null, relayoutMediaGrid_id2, "RangeChanged", "id2");
  adjustLineHeightIfTooBig("id3");
  adjustFontSizeIfTooBig("id3");
  Widget.onload();
  initializeMediaStream_id2();
  performPostEffectsFixups();
}
function onPageUnload() {
  Widget.onunload();
}
