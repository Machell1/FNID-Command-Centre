export default function Footer() {
  return (
    <footer className="text-white-50 py-3 mt-4" style={{ backgroundColor: '#1F3864' }} role="contentinfo">
      <div className="container-fluid">
        <div className="row align-items-center text-center text-md-start">
          <div className="col-md-5">
            <small>
              <i className="bi bi-shield-shaded me-1"></i>
              Jamaica Constabulary Force | Firearms & Narcotics Investigation Division | Area 3
            </small>
          </div>
          <div className="col-md-4 text-md-center">
            <small>Manchester | St. Elizabeth | Clarendon</small>
          </div>
          <div className="col-md-3 text-md-end">
            <small className="text-white-50">RESTRICTED - Official Use Only</small>
          </div>
        </div>
      </div>
    </footer>
  );
}
